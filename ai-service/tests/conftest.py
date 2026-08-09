"""让 tests/ 下的用例能直接 import ai-service 根目录的模块（scoring/fusion/...）。

pytest 默认把 test 文件所在目录加入 sys.path，但那些模块在上级目录，
这里把 ai-service 根目录插到最前，避免依赖 PYTHONPATH 环境变量。
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
