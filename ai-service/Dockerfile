FROM python:3.13-slim

WORKDIR /app

# 升级 pip（解决旧版 pip 和最新包的兼容问题）
RUN pip install --upgrade pip

# 安装依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 预下载 embedding 模型（避免每次启动都下载 400MB）
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('shibing624/text2vec-base-chinese')"

# 复制代码
COPY . .

EXPOSE 5000

CMD ["python", "main.py"]
