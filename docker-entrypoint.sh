#!/usr/bin/env bash
set -e

# Auto-generate default config if missing
if [ ! -f "config.yaml" ]; then
    echo "[ENTRYPOINT] config.yaml not found. Generating from config.example.yaml..."
    cp config.example.yaml config.yaml
fi

# Auto-download YOLOv11n ONNX if missing
mkdir -p models snapshots
if [ ! -f "models/yolo11n.onnx" ]; then
    echo "[ENTRYPOINT] Downloading YOLOv11n ONNX weights..."
    curl -sL "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.onnx" -o "models/yolo11n.onnx" || echo "[ENTRYPOINT] Download failed. Falling back to synthetic detector."
fi

exec "$@"
