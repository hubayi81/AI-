"""
鞋类知识库检索器。

启动时读取 knowledge/*.md，按 ## 标题分块，向量化后常驻内存。
和 ShoeRetriever 共用同一个 embedding 模型，不额外加载模型。
"""
import re
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

# — 全局模型，和 retriever.py 共用同一个 —
_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("shibing624/text2vec-base-chinese")
    return _model


class KnowledgeBase:
    """鞋类知识库：按 ## 标题分块，语义检索"""

    def __init__(self, knowledge_dir: str = None):
        if knowledge_dir is None:
            # 默认在 knowledge_base.py 同级目录下的 knowledge/ 文件夹
            knowledge_dir = Path(__file__).parent / "knowledge"

        self.chunks: list[dict] = []       # 每个元素: {"text": ..., "source": 文件名, "heading": 标题}
        self.embeddings: np.ndarray = None

        self._load(knowledge_dir)

    # ——— 加载与分块 ———

    def _load(self, knowledge_dir: str):
        knowledge_path = Path(knowledge_dir)
        if not knowledge_path.exists():
            print(f"[KnowledgeBase] 知识目录不存在: {knowledge_dir}")
            return

        md_files = sorted(knowledge_path.glob("*.md"))
        if not md_files:
            print(f"[KnowledgeBase] 知识目录下无 markdown 文件: {knowledge_dir}")
            return

        for md_file in md_files:
            self._parse_file(md_file)

        if not self.chunks:
            return

        # 所有 chunk 向量化（一次编码，省去逐条 encode 的开销）
        model = _get_model()
        texts = [c["text"] for c in self.chunks]
        self.embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

        print(f"[KnowledgeBase] 加载完成：{len(md_files)} 个文件 → {len(self.chunks)} 个知识块")

    def _parse_file(self, file_path: Path):
        """解析单个 markdown 文件，按 ## 标题分块。
        为什么按 ## 而不是固定字数？—— 每个 ## 标题是一个独立的知识点，
        按标题分块保证语义完整，不会把'扁平足的选鞋要点'切成两半。"""
        content = file_path.read_text(encoding="utf-8")
        source = file_path.name  # 如 "01-材质科技.md"

        # 按 ## 切割（# 是一级标题，## 是二级标题）
        # 每个 block 包含 "标题\n内容"
        blocks = re.split(r"\n(?=## )", content)

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # 提取二级标题文本（去掉 ## 前缀）
            heading = ""
            lines = block.split("\n", 1)
            if lines[0].startswith("## "):
                heading = lines[0][3:].strip()

            # 跳过纯一级标题块（只有 # 开头，没有 ##）
            if not heading:
                continue

            # 构建可检索的文本：文件名 + 标题 + 内容
            file_label = source.replace(".md", "").replace("-", " · ")

            self.chunks.append({
                "text": block,                      # 完整 markdown 块（给 LLM 看的）
                "heading": heading,                 # 标题（用于前端展示来源）
                "source": file_label,               # 来源文件名（让用户知道出处）
            })

    # ——— 检索 ———

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """语义检索知识库，返回 top_k 个最相关的知识块"""
        if not query or self.embeddings is None:
            return []

        model = _get_model()
        query_vec = model.encode([query], convert_to_numpy=True, show_progress_bar=False)

        # 余弦相似度（向量已归一化，内积等价余弦相似度）
        similarities = np.dot(self.embeddings, query_vec.T).flatten()
        indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for i in indices:
            chunk = self.chunks[i].copy()
            chunk["score"] = float(similarities[i])
            results.append(chunk)

        return results
