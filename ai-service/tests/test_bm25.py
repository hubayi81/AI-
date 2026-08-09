"""knowledge_base.BM25Retriever 纯函数单测（中文友好 BM25，无嵌入依赖）。"""
from knowledge_base import BM25Retriever


def test_tokenize_chinese_bigram():
    bm = BM25Retriever(["x"])
    toks = bm._tokenize("缓震跑鞋")
    # 含字 "缓震跑鞋" 整体 + bigram "缓震"/"震跑"/"跑鞋"
    assert "缓震" in toks and "跑鞋" in toks


def test_tokenize_english_lowercase():
    bm = BM25Retriever(["x"])
    toks = bm._tokenize("Nike Air")
    assert "nike" in toks and "air" in toks


def test_score_rewards_matching_terms():
    docs = ["缓震跑鞋适合日常训练", "篮球鞋高帮设计", "帆布鞋百搭"]
    bm = BM25Retriever(docs)
    s_hit = bm.score("缓震跑鞋", 0)
    s_miss = bm.score("篮球鞋", 0)
    assert s_hit > s_miss  # 文档0更匹配"缓震跑鞋"


def test_search_returns_ranked_topk():
    docs = ["Nike 缓震跑鞋", "Adidas 篮球鞋", "Converse 帆布鞋",
            "Asics 支撑跑鞋", "On 缓震路跑鞋"]
    bm = BM25Retriever(docs)
    out = bm.search("缓震跑鞋", top_k=2)
    ids = [i for i, _ in out]
    # 文档0和文档4都含"缓震"，应排前二
    assert set(ids) == {0, 4}


def test_search_drops_zero_score():
    docs = ["苹果手机", "香蕉水果"]
    bm = BM25Retriever(docs)
    out = bm.search("跑鞋", top_k=5)
    # 无重叠 → 无正分结果
    assert out == []


def test_empty_documents_no_crash():
    bm = BM25Retriever([])
    assert bm.search("x", top_k=5) == []
