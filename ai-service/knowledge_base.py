"""
鞋类知识库 — 三层 RAG 增强版。

Layer 1（深度解析）：按 ## 标题分块 + ### 子块索引 + 关键词自动提取
Layer 2（混合检索）：向量语义检索 + BM25 关键词检索 → 加权融合 → 重排序
Layer 3（生成校验）：相似度阈值过滤 + 来源多样性 + 置信度标注

和 ShoeRetriever 共用同一个 embedding 模型，不额外加载模型。
"""

import math
import re
from collections import Counter
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from fusion import rrf_fuse

# ─── 全局 embedding 模型 ───
_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("shibing624/text2vec-base-chinese")
    return _model


# ═══════════════════════════════════════════════
#  BM25 关键词检索器（纯 Python，零外部依赖）
# ═══════════════════════════════════════════════

class BM25Retriever:
    """轻量 BM25 实现。中文用字级别 bigram + 词级别分词，无需 jieba。"""

    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents = documents
        self.N = len(documents)
        if self.N == 0:
            self.tokens_list, self.doc_lens, self.avgdl, self.idf = [], [], 1, {}
            return

        self.tokens_list = [self._tokenize(d) for d in documents]
        self.doc_lens = [len(t) for t in self.tokens_list]
        self.avgdl = sum(self.doc_lens) / self.N

        # IDF
        df = {}
        for tokens in self.tokens_list:
            for w in set(tokens):
                df[w] = df.get(w, 0) + 1
        self.idf = {}
        for w, f in df.items():
            self.idf[w] = math.log((self.N - f + 0.5) / (f + 0.5) + 1)

    def _tokenize(self, text: str) -> list[str]:
        """中文友好分词：拆出中文字 + 英文单词 + 数字，中文额外加 bigram"""
        text = text.lower()
        # 分离中文连续块、英文单词、数字
        tokens = re.findall(r"[一-鿿]+|[a-z0-9]+", text)
        result = list(tokens)
        # 中文块拆 bigram（字级别，对短 query 友好）
        for t in tokens:
            if re.match(r"^[一-鿿]+$", t) and len(t) >= 2:
                for i in range(len(t) - 1):
                    result.append(t[i:i + 2])
        return result

    def score(self, query: str, doc_idx: int) -> float:
        q_tokens = self._tokenize(query)
        score = 0.0
        dl = self.doc_lens[doc_idx]
        for t in q_tokens:
            if t not in self.idf:
                continue
            tf = self.tokens_list[doc_idx].count(t)
            idf = self.idf[t]
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            score += idf * numerator / denominator
        return score

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        if self.N == 0:
            return []
        scores = [(i, self.score(query, i)) for i in range(self.N)]
        ranked = sorted(scores, key=lambda x: -x[1])
        return [(i, s) for i, s in ranked[:top_k] if s > 0]


# ═══════════════════════════════════════════════
#  KnowledgeBase — 三层 RAG
# ═══════════════════════════════════════════════

class KnowledgeBase:
    """鞋类知识库：深度解析 → 混合检索 → 重排序 → 置信度标注"""

    # 混合检索权重：向量 0.6 / 关键词 0.4
    VECTOR_WEIGHT = 0.6
    BM25_WEIGHT = 0.4
    # 相似度阈值：低于此值直接丢弃
    MIN_SCORE = 0.35
    # 同一来源最多几个块（来源多样性）
    MAX_PER_SOURCE = 2

    def __init__(self, knowledge_dir: str = None):
        if knowledge_dir is None:
            knowledge_dir = Path(__file__).parent / "knowledge"

        self.chunks: list[dict] = []          # 主知识块（## 级别）
        self.sub_chunks: list[dict] = []      # 子块索引（### 级别，指向父块）
        self.embeddings: np.ndarray = None    # 向量索引
        self.bm25: BM25Retriever | None = None

        self._load(knowledge_dir)

    # ─── Layer 1：深度解析 ───

    def _load(self, knowledge_dir: str):
        path = Path(knowledge_dir)
        if not path.exists():
            print(f"[KnowledgeBase] 知识目录不存在: {knowledge_dir}")
            return

        md_files = sorted(path.glob("*.md"))
        if not md_files:
            return

        for md_file in md_files:
            self._parse_file(md_file)

        if not self.chunks:
            return

        # 向量化主块
        model = _get_model()
        texts = [c["text"] for c in self.chunks]
        self.embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

        # 构建 BM25 索引（主块内容）
        self.bm25 = BM25Retriever([c["text"] for c in self.chunks])

        # 统计：主块数 + 子块数
        sub_count = sum(1 for c in self.chunks if c.get("subs"))
        print(f"[KnowledgeBase] 加载完成：{len(md_files)} 文件 → "
              f"{len(self.chunks)} 主块 + {sub_count} 含子块")

    def _parse_file(self, file_path: Path):
        """按 ## 分主块，### 分子块。主块可独立检索，子块附属于主块——检索命中子块时
        把整个主块返回，保证上下文完整。"""
        content = file_path.read_text(encoding="utf-8")
        source_name = file_path.name

        # 提取一级标题作为领域标签
        domain = ""
        m = re.match(r"^# (.+)", content)
        if m:
            domain = m.group(1).strip()

        # 按 ## 切割主块
        blocks = re.split(r"\n(?=## )", content)

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # 提取 ## 标题
            heading = ""
            lines = block.split("\n", 1)
            if lines[0].startswith("## "):
                heading = lines[0][3:].strip()

            if not heading:
                continue  # 跳过纯 # 块

            # 提取 ### 子标题作为关键词标签
            subs = re.findall(r"^### (.+)", block, re.MULTILINE)
            tags = self._extract_tags(heading, block, subs, domain)

            source_label = source_name.replace(".md", "").replace("-", " · ")

            chunk = {
                "text": block,
                "heading": heading,
                "source": source_label,
                "domain": domain,             # 一级标题（领域）
                "tags": tags,                 # 自动提取的关键词
                "subs": subs,                 # ### 子标题列表
            }
            self.chunks.append(chunk)

            # 子块索引：每个 ### 也是一个可检索单元，但指向父块
            sub_blocks = re.split(r"\n(?=### )", block)
            for sb in sub_blocks:
                sb = sb.strip()
                sm = re.match(r"^### (.+)", sb)
                if not sm:
                    continue
                sub_heading = sm.group(1).strip()
                self.sub_chunks.append({
                    "text": sb,
                    "heading": sub_heading,
                    "parent_heading": heading,
                    "source": source_label,
                    "parent_idx": len(self.chunks) - 1,  # 指向父块
                    "tags": self._extract_tags(sub_heading, sb, [], domain),
                })

    def _extract_tags(self, heading: str, block: str, subs: list[str],
                      domain: str) -> list[str]:
        """从标题 + 内容 + 子标题中提取关键词标签"""
        tags = [heading]
        for s in subs:
            tags.append(s)
        if domain:
            tags.append(domain)

        # 匹配常见专业术语
        terms = set()
        term_patterns = [
            r"(缓震|支撑|透气|防水|耐磨|轻量|宽楦|窄楦|扁平足|高足弓|宽脚|窄脚)",
            r"(EVA|TPU|Boost|Air\s*Max|Gore.?Tex|Flyknit|Primeknit|碳板|气垫)",
            r"(跑鞋|篮球鞋|休闲鞋|越野|登山|帆布鞋|板鞋|老爹鞋|竞速)",
            r"(Nike|Adidas|ASICS|New\s*Balance|Converse|Vans|Crocs|Puma|On)",
        ]
        for pat in term_patterns:
            for m in re.findall(pat, block, re.IGNORECASE):
                if isinstance(m, tuple):
                    m = "".join(m)
                terms.add(m.strip())

        tags.extend(sorted(terms))
        # 去重保留顺序
        seen = set()
        unique = []
        for t in tags:
            t = t.strip()
            if t and t not in seen:
                unique.append(t)
                seen.add(t)
        return unique

    # ─── Layer 2：混合检索 + 重排序 ───

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """混合检索：向量语义 + BM25 关键词 → 加权融合 → 重排序 → 阈值过滤"""
        if not query or self.embeddings is None:
            return []

        # — 向量检索 —
        vec_results = self._vector_search(query, top_k * 3)
        # — BM25 关键词检索 —
        bm25_results = self._bm25_search(query, top_k * 3)

        # — 加权融合（Reciprocal Rank Fusion）—
        fused = self._rrf_fusion(vec_results, bm25_results, top_k)

        # — 重排序 —
        reranked = self._rerank(fused)

        # — 阈值过滤 —
        return self._filter_and_format(reranked, top_k)

    def _vector_search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        model = _get_model()
        query_vec = model.encode([query], convert_to_numpy=True, show_progress_bar=False)
        similarities = np.dot(self.embeddings, query_vec.T).flatten()
        indices = np.argsort(similarities)[::-1][:top_k]
        return [(int(i), float(similarities[i])) for i in indices]

    def _bm25_search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        if self.bm25 is None:
            return []
        return self.bm25.search(query, top_k)

    def _rrf_fusion(self, vec: list[tuple[int, float]],
                    bm25: list[tuple[int, float]], top_k: int
                    ) -> list[tuple[int, float]]:
        """Reciprocal Rank Fusion：向量结果和 BM25 结果加权合并。
        实现在 fusion.rrf_fuse —— 评测脚本用的是同一个函数，
        保证"评测的东西"和"线上跑的东西"是同一份代码。"""
        return rrf_fuse(
            [[idx for idx, _ in vec], [idx for idx, _ in bm25]],
            weights=[self.VECTOR_WEIGHT, self.BM25_WEIGHT],
            top_n=top_k * 2,
        )

    def _rerank(self, fused: list[tuple[int, float]]
                ) -> list[tuple[int, float, str]]:
        """重排序策略：
        1. 丢弃低于 MIN_SCORE 的结果
        2. 同一来源（source）最多 MAX_PER_SOURCE 个，超出部分降权
        3. 返回排序结果"""
        filtered: list[tuple[int, float, str]] = []

        if not fused:
            return []
        # RRF 分数天然极小（k=60 时约 weight/(rank+60) ≈ 0.01~0.02），
        # 必须先归一化到 0-1 才能和 MIN_SCORE(0.35) 比较，否则所有结果都会被阈值丢弃。
        max_score = max(s for _, s in fused) or 1.0

        for idx, raw in fused:
            score = raw / max_score  # 归一化到 0-1，rank0 的块为 1.0
            if score < self.MIN_SCORE:
                continue
            filtered.append((idx, score, self.chunks[idx]["source"]))

        # 来源多样性重排
        reranked: list[tuple[int, float, str]] = []
        source_count: dict[str, int] = {}

        for idx, score, src in filtered:
            cnt = source_count.get(src, 0)
            if cnt >= self.MAX_PER_SOURCE:
                # 超出的块降权 30%
                score *= 0.7
            source_count[src] = cnt + 1
            reranked.append((idx, score, src))

        # 按调整后的分数重新排序
        reranked.sort(key=lambda x: -x[1])
        return reranked

    # ─── Layer 3：阈值过滤 + 置信度标注 ───

    def _filter_and_format(self, reranked: list[tuple[int, float, str]],
                           top_k: int) -> list[dict]:
        """格式化为最终输出，附带置信度标注和子块引用"""
        results = []

        for idx, score, src in reranked[:top_k]:
            chunk = self.chunks[idx].copy()

            # 置信度分级（score 已是 0-1 归一化值；RRF 区间窄，故用相对阈值）
            # 注：更可信的置信度（向量余弦 + 命中路数）将在评分系统化阶段重做
            if score >= 0.9:
                confidence = "high"
            elif score >= 0.6:
                confidence = "medium"
            else:
                confidence = "low"

            # 如果有子块，附带最相关的一个子块标题
            related_sub = None
            if chunk.get("subs"):
                related_sub = chunk["subs"][0] if len(chunk["subs"]) == 1 else None

            results.append({
                "content": chunk["text"],
                "heading": chunk["heading"],
                "source": chunk["source"],
                "domain": chunk.get("domain", ""),
                "tags": chunk.get("tags", []),
                "related_sub": related_sub,
                "confidence": confidence,
                "score": round(score, 4),
            })

        return results
