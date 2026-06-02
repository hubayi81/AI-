import numpy as np
from sentence_transformers import SentenceTransformer

# 全局模型，只加载一次
_model = None

def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("shibing624/text2vec-base-chinese")
    return _model


class ShoeRetriever:
    """商品语义检索器——用 embedding 做语义匹配，不再依赖关键词命中文"""

    def __init__(self, products: list[dict]):
        self.products = products
        if not products:
            self.embeddings = None
            return
        model = _get_model()
        texts = []
        for p in products:
            name = p.get("name", "")
            desc = p.get("description", "")
            texts.append(f"{name} {desc}" if desc else name)
        self.embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    def search(self, query: str, top_k: int = 20) -> list[dict]:
        """语义搜索，返回 top_k 最相关商品"""
        if not query or self.embeddings is None:
            return self.products[:top_k]

        model = _get_model()
        query_vec = model.encode([query], convert_to_numpy=True, show_progress_bar=False)

        # 余弦相似度（已归一化的 embedding 用内积等价余弦相似度）
        similarities = np.dot(self.embeddings, query_vec.T).flatten()
        indices = np.argsort(similarities)[::-1][:top_k]

        return [self.products[i] for i in indices]
