#!/usr/bin/env bash
set -e

echo "=========================================================="
echo " SMART SENTRY VISION - 1-CLICK DOCKER LAUNCHER"
echo "=========================================================="

if [ ! -f "config.yaml" ]; then
    echo "[1/3] Creating config.yaml from template..."
    cp config.example.yaml config.yaml
    echo "       -> Please edit config.yaml to set your Telegram bot_token and chat_id."
else
    echo "[1/3] Found existing config.yaml."
fi

if [ ! -f "models/yolo11n.onnx" ]; then
    echo "[2/3] Downloading YOLOv11n ONNX weights..."
    ./scripts/download_models.sh
else
    echo "[2/3] Found YOLOv11n ONNX model."
fi

echo "[3/3] Building and starting Docker container..."
docker compose up -d

echo ""
echo "=========================================================="
echo " SENTRY CONTAINER IS RUNNING!"
echo " Web Dashboard:  http://localhost:8080"
echo " Live Video:     http://localhost:8080/video/stream"
echo " REST Status:    http://localhost:8080/api/status"
echo " View logs:      docker compose logs -f"
echo " Stop:           docker compose down"
echo "=========================================================="
