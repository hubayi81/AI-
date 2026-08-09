"""knowledge_base.KnowledgeBase._rerank 归一化单测。

核心 bug 来源（已修）：RRF 分数天然极小（k=60 时约 1/60≈0.0167），
若直接和固定阈值 MIN_SCORE=0.35 比较，所有结果都会被阈值丢弃。
_rrank 必须先归一化到 0-1（rank0 的块为 1.0）再比较。

本测试构造极小 RRF 分数，验证：
  - 归一化后 rank0 被保留；
  - 归一化分数低于 MIN_SCORE 的块被丢弃（而非全部丢弃）。
"""
import tempfile
from pathlib import Path

from knowledge_base import KnowledgeBase


def _build_kb_with_two_blocks():
    d = tempfile.mkdtemp()
    md = Path(d) / "kb.md"
    md.write_text(
        "# 测试知识域\n"
        "## 块A\n缓震跑鞋适合日常训练，Zoom Air 气垫。\n"
        "## 块B\n宽楦鞋适合宽脚人群，2E/4E 可选。\n",
        encoding="utf-8",
    )
    return KnowledgeBase(str(d))


def test_rerank_keeps_top_block_and_drops_low():
    kb = _build_kb_with_two_blocks()
    # RRF 原始分数极小：块0=0.016，块1=0.002
    # 归一化：块0=1.0(>0.35 保留)，块1=0.002/0.016=0.125(<0.35 丢弃)
    fused = [(0, 0.016), (1, 0.002)]
    out = kb._rerank(fused)
    kept_ids = [idx for idx, _, _ in out]
    assert kept_ids == [0]  # 只有块0 存活，证明"不是全部丢弃"


def test_rerank_normalizes_rank0_to_one():
    kb = _build_kb_with_two_blocks()
    fused = [(0, 0.016), (1, 0.012)]
    out = kb._rerank(fused)
    # 归一化后 rank0 分数应为 1.0
    assert out[0][1] == 1.0


def test_rerank_empty_input():
    kb = _build_kb_with_two_blocks()
    assert kb._rerank([]) == []
