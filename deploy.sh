#!/bin/bash
# ===== AI 鞋类导购助手 — 一键部署到阿里云 =====
# 用法：./deploy.sh
# 前提：服务器上已安装 Docker

set -e

SERVER="101.132.37.107"
PROJECT_DIR="/opt/aishoes"

echo "===== 1. 本地构建镜像 ====="
docker build -t shoe-ai:latest ./ai-service
docker build -t shoe-app:latest ./aishoesrecommend

echo ""
echo "===== 2. 传输文件到服务器 ====="
ssh root@$SERVER "mkdir -p $PROJECT_DIR"
scp docker-compose.yml docker-init.sql .env root@$SERVER:$PROJECT_DIR/

echo ""
echo "===== 3. 导出镜像并传输 ====="
docker save shoe-ai:latest shoe-app:latest | ssh root@$SERVER "docker load"

echo ""
echo "===== 4. 服务器上启动服务 ====="
ssh root@$SERVER "cd $PROJECT_DIR && docker compose down 2>/dev/null; docker compose up -d"

echo ""
echo "===== ✅ 部署完成 ====="
echo "访问地址：http://$SERVER:8080/login.html"
echo "管理员账号：admin / 123456"
echo ""
echo "查看日志：ssh root@$SERVER 'cd $PROJECT_DIR && docker compose logs -f'"
