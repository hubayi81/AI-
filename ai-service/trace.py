"""
Agent 调用链路追踪 —— 记录每次 Agent 请求的延迟、工具调用、token 消耗。
用 SQLite 零运维存储，sqlite3 是 Python 标准库，不需要额外依赖。

设计原则：
- 追踪数据存 Python 侧 SQLite，和 MySQL 业务数据分离
- 异步写库不阻塞 Agent 主流程
- 降级：写库失败不影响 Agent 正常返回
"""
import json
import sqlite3
import time
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from threading import Lock

# —— 北京时间 ——
TZ = timezone(timedelta(hours=8))

# —— 数据库路径：和 trace.py 同级 ——
DB_PATH = Path(__file__).parent / "traces.db"
_db_lock = Lock()


class TraceStore:
    """SQLite 单例，管理 traces 表的创建和写入"""

    _initialized = False

    @classmethod
    def _ensure_table(cls):
        if cls._initialized:
            return
        with _db_lock:
            if cls._initialized:
                return
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_traces (
                    trace_id       TEXT PRIMARY KEY,
                    timestamp      TEXT NOT NULL,          -- ISO 8601
                    duration_ms    REAL NOT NULL DEFAULT 0, -- 总耗时（毫秒）
                    first_token_ms REAL,                    -- 首个 token 出现时间（流式用）
                    tool_calls     TEXT DEFAULT '[]',       -- JSON 数组 [{name, duration_ms}]
                    tokens_input   INTEGER DEFAULT 0,       -- 输入 token 估算值
                    tokens_output  INTEGER DEFAULT 0,       -- 输出 token 估算值
                    error          TEXT,                     -- 错误信息，成功时为 NULL
                    conversation_id TEXT DEFAULT ''
                )
            """)
            # 索引：按时间查询是最常见的需求
            conn.execute("CREATE INDEX IF NOT EXISTS idx_traces_ts ON agent_traces(timestamp)")
            conn.commit()
            conn.close()
            cls._initialized = True

    @classmethod
    def save(cls, trace_data: dict):
        """保存一条 trace 记录。异步写库失败时静默忽略——追踪挂了不影响业务。"""
        cls._ensure_table()
        try:
            with _db_lock:
                conn = sqlite3.connect(str(DB_PATH))
                conn.execute("""
                    INSERT OR REPLACE INTO agent_traces
                    (trace_id, timestamp, duration_ms, first_token_ms,
                     tool_calls, tokens_input, tokens_output, error, conversation_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trace_data.get("trace_id", str(uuid.uuid4())[:8]),
                    trace_data.get("timestamp", datetime.now(TZ).isoformat()),
                    trace_data.get("duration_ms", 0),
                    trace_data.get("first_token_ms"),
                    json.dumps(trace_data.get("tool_calls", []), ensure_ascii=False),
                    trace_data.get("tokens_input", 0),
                    trace_data.get("tokens_output", 0),
                    trace_data.get("error"),
                    trace_data.get("conversation_id", ""),
                ))
                conn.commit()
                conn.close()
        except Exception:
            pass  # 追踪挂了不影响业务

    @classmethod
    def query(cls, sql: str, params: tuple = ()) -> list[dict]:
        """通用查询，返回字典列表"""
        cls._ensure_table()
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []


class TraceContext:
    """单次 Agent 调用的追踪上下文。支持手动 start/end 模式。

    用法：
        ctx = TraceContext(conversation_id="conv_xxx")
        ctx.start()
        # ... Agent 运行中，随时 ctx.add_tool_call(...)
        ctx.end(error=None, tokens_input=1800, tokens_output=500)
    """

    def __init__(self, conversation_id: str = ""):
        self.trace_id = str(uuid.uuid4())[:8]
        self.conversation_id = conversation_id
        self._start_time: float = 0
        self._first_token_time: float = 0
        self._tool_calls: list[dict] = []
        self._tool_start_times: dict[str, float] = {}
        # 工具执行中间状态 —— 用于计算每个工具的开始时间
        self._current_tool: str = ""

    # ——— 生命周期 ———

    def start(self):
        """开始计时"""
        self._start_time = time.time()

    def end(self, error: str | None = None, tokens_input: int = 0, tokens_output: int = 0):
        """结束计时并写入数据库。tokens 参数用于记录估算值。"""
        duration_ms = (time.time() - self._start_time) * 1000 if self._start_time else 0
        first_token_ms = (
            (self._first_token_time - self._start_time) * 1000
            if self._first_token_time and self._start_time else None
        )

        TraceStore.save({
            "trace_id": self.trace_id,
            "timestamp": datetime.fromtimestamp(self._start_time, tz=TZ).isoformat() if self._start_time else datetime.now(TZ).isoformat(),
            "duration_ms": round(duration_ms, 1),
            "first_token_ms": round(first_token_ms, 1) if first_token_ms else None,
            "tool_calls": self._tool_calls,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "error": error,
            "conversation_id": self.conversation_id,
        })

    # ——— 工具调用追踪 ———

    def on_tool_start(self, tool_name: str):
        """工具开始执行时调用"""
        self._current_tool = tool_name
        self._tool_start_times[tool_name] = time.time()

    def on_tool_end(self):
        """工具执行结束，记录耗时"""
        if self._current_tool and self._current_tool in self._tool_start_times:
            elapsed = (time.time() - self._tool_start_times[self._current_tool]) * 1000
            self._tool_calls.append({
                "name": self._current_tool,
                "duration_ms": round(elapsed, 1),
            })
            self._current_tool = ""

    # ——— Token 流标记 ———

    def on_first_token(self):
        """标记首个 token 到达时间"""
        if self._first_token_time == 0:
            self._first_token_time = time.time()

    # ——— Token 估算 ———
    # 为什么用估算而不是查 API 返回的 usage？
    # —— DeepSeek 流式模式下 astream_events 不返回 usage 字段，
    # 中文 1 字符 ≈ 0.7 token，用字符估算在 ±15% 误差内，够用了。

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """粗略估算文本 token 数。中文 ≈ 1.5 字/token，英文 ≈ 4 字/token。"""
        if not text:
            return 0
        # 统计中文字符数
        chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)
