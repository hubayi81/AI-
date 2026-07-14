import hashlib
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
    """商品语义检索器——用 embedding 做语义匹配，不再依赖关键词命中"""

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


# ===== 向量索引缓存 =====
# 为什么需要缓存？—— 之前每次请求都 new ShoeRetriever(products)，
# 353 个商品的向量化每次都要跑一遍（~80ms）。缓存后首次构建，
# 后续请求直接复用，10 并发也只建一次。
# 为什么用商品 ID 做 key？—— 商品数据更新（增删改）后 ID 列表变了，
# 自动触发缓存 miss 重建索引。

_retriever_cache: dict[str, ShoeRetriever] = {}


def _make_cache_key(products: list[dict]) -> str:
    """用商品 ID 列表的 hash 作为缓存 key。ID 变了 → 自动重建。"""
    ids = sorted(str(p.get("id", 0)) for p in products)
    return hashlib.md5(",".join(ids).encode()).hexdigest()


def get_retriever(products: list[dict]) -> ShoeRetriever:
    """获取缓存的检索器。商品列表不变时复用已有索引。"""
    if not products:
        return ShoeRetriever([])
    key = _make_cache_key(products)
    if key not in _retriever_cache:
        _retriever_cache[key] = ShoeRetriever(products)
    return _retriever_cache[key]


def clear_retriever_cache():
    """商品数据更新后清除缓存（管理员增删改时调用）"""
    _retriever_cache.clear()
