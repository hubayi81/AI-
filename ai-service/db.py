"""
商品数据访问（架构 A）：Python 直连 MySQL 读商品，
消除 Java 每请求把 353 个商品全量序列化过 HTTP 搬运的反模式。

- Redis 缓存商品列表（TTL 300s），多 worker 共享、重启不丢
- MySQL 不可用时返回空列表，调用方降级到传入的 products 或提示
- 管理员增删商品后调用 refresh_products_cache() 主动失效缓存
"""
import json
import os
from dotenv import load_dotenv

import pymysql
import redis

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "aishoes")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

_PRODUCTS_CACHE_KEY = "shoe:products:all"
_FEEDBACK_CACHE_KEY = "shoe:feedback:weights"
_CACHE_TTL = 300  # 秒

# 贝叶斯平滑强度：相当于给每个商品先垫 ALPHA 次"全局平均水平"的虚拟反馈。
# 值越大，小样本商品越难偏离全局均值（抗噪），但真实信号也收敛得越慢。
_FEEDBACK_ALPHA = 10.0


def _get_redis() -> redis.Redis | None:
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
                        socket_connect_timeout=2, socket_timeout=2, decode_responses=False)
        r.ping()
        return r
    except Exception:
        return None


def _query_mysql() -> list[dict]:
    try:
        conn = pymysql.connect(host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
                               password=MYSQL_PASSWORD, database=MYSQL_DATABASE,
                               charset="utf8mb4", connect_timeout=3)
    except Exception as e:
        print(f"[db] 连接 MySQL 失败: {e}")
        return []
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT id, name, brand, category, gender, price, "
                "description, color, size_range, stock, image_url "
                "FROM shoe_product"
            )
            rows = cur.fetchall()
        products = []
        for r in rows:
            d = dict(r)
            # Decimal -> float，保证后续 json 序列化与评分计算正常
            if d.get("price") is not None:
                d["price"] = float(d["price"])
            products.append(d)
        return products
    except Exception as e:
        print(f"[db] 查询商品失败: {e}")
        return []
    finally:
        conn.close()


def load_products() -> list[dict]:
    """加载全部商品：优先 Redis 缓存，miss 则查 MySQL 并写回缓存。"""
    r = _get_redis()
    if r:
        try:
            cached = r.get(_PRODUCTS_CACHE_KEY)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
    products = _query_mysql()
    if products and r:
        try:
            r.setex(_PRODUCTS_CACHE_KEY, _CACHE_TTL,
                    json.dumps(products, ensure_ascii=False))
        except Exception:
            pass
    return products


def refresh_products_cache() -> None:
    """管理员增删商品后调用，主动失效商品缓存。"""
    r = _get_redis()
    if r:
        try:
            r.delete(_PRODUCTS_CACHE_KEY)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 反馈权重：把 👍/👎 变成排序信号（冷启动安全）
# ---------------------------------------------------------------------------

def _query_feedback_stats() -> list[dict]:
    """按商品聚合 like / dislike 计数。

    依赖 ai_feedback_item 表（一次反馈 × 一个商品 = 一行）。
    为什么不在 ai_feedback 里存逗号分隔的 product_ids？
      —— 那样聚合要写 FIND_IN_SET，走不了索引、也无法 GROUP BY，
         数据一多就是全表扫描。范式化多一张表，聚合才是一条 SQL。
    """
    try:
        conn = pymysql.connect(host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
                               password=MYSQL_PASSWORD, database=MYSQL_DATABASE,
                               charset="utf8mb4", connect_timeout=3)
    except Exception as e:
        print(f"[db] 反馈统计连接 MySQL 失败: {e}")
        return []
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT product_id, "
                "SUM(feedback = 'like') AS likes, "
                "SUM(feedback = 'dislike') AS dislikes "
                "FROM ai_feedback_item GROUP BY product_id"
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        # 表不存在（老库未迁移）也走这里，静默降级为"无反馈数据"
        print(f"[db] 查询反馈统计失败（可忽略，将退化为纯内容评分）: {e}")
        return []
    finally:
        conn.close()


def _compute_weights(rows: list[dict]) -> dict[str, float]:
    """把原始计数换算成 [-0.5, 0.5] 区间的相对偏好权重。

    公式（贝叶斯平滑 / m-estimate）：
        mu      = 全局好评率            （所有商品的 likes / 总反馈数）
        p_hat_i = (likes_i + α·mu) / (n_i + α)
        w_i     = p_hat_i - mu

    为什么这么算，而不是直接用 likes - dislikes 或 likes/(likes+dislikes)？
      1. 直接相减：10 赞 0 踩 和 100 赞 90 踩 都是 +10，显然不对。
      2. 直接算比率：1 赞 0 踩 = 100% 好评，会把只被点过一次的商品顶到第一。
      3. 平滑后，n=0 时 p_hat = mu → w = 0 → 冷启动商品不加不减，
         评分自动退化为 B 阶段的纯内容分。这是这套设计的关键性质。

    备选方案是 Wilson score lower bound，但它是单侧置信下界、
    对"踩"的惩罚不对称，更适合纯正向排序（如 Reddit 顶帖），
    这里需要赞和踩对称生效，所以选了 m-estimate。
    """
    total_like = sum(float(r.get("likes") or 0) for r in rows)
    total_dis = sum(float(r.get("dislikes") or 0) for r in rows)
    total = total_like + total_dis
    if total <= 0:
        return {}
    mu = total_like / total

    weights: dict[str, float] = {}
    for r in rows:
        pid = r.get("product_id")
        if pid is None:
            continue
        likes = float(r.get("likes") or 0)
        dislikes = float(r.get("dislikes") or 0)
        n = likes + dislikes
        p_hat = (likes + _FEEDBACK_ALPHA * mu) / (n + _FEEDBACK_ALPHA)
        weights[str(pid)] = round(p_hat - mu, 4)
    return weights


def load_feedback_weights() -> dict[str, float]:
    """加载各商品的反馈权重 {product_id(str): weight}。

    缓存 TTL 300s：反馈是排序先验，不是实时 UI 状态，
    最多 5 分钟生效延迟可接受，换来的是不用在 Java 侧再耦合一套缓存失效逻辑。
    任何一步失败都返回 {}，调用方拿到空字典即等价于"没有反馈数据"。
    """
    r = _get_redis()
    if r:
        try:
            cached = r.get(_FEEDBACK_CACHE_KEY)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
    weights = _compute_weights(_query_feedback_stats())
    if r:
        try:
            r.setex(_FEEDBACK_CACHE_KEY, _CACHE_TTL,
                    json.dumps(weights, ensure_ascii=False))
        except Exception:
            pass
    return weights
