#!/bin/bash
set -e

MODEL_DIR="models"
mkdir -p "$MODEL_DIR"

YOLO11N_URL="https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.onnx"

echo "=========================================================="
echo " DOWNLOADING YOLOv11-NANO ONNX MODEL"
echo "=========================================================="

if [ -f "$MODEL_DIR/yolo11n.onnx" ]; then
    echo "Model already exists at $MODEL_DIR/yolo11n.onnx"
else
    echo "Downloading YOLOv11n ONNX from $YOLO11N_URL..."
    curl -L "$YOLO11N_URL" -o "$MODEL_DIR/yolo11n.onnx"
    echo "Downloaded successfully to $MODEL_DIR/yolo11n.onnx"
fi
