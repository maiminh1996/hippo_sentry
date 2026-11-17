from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Tuple, Union
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path("config.yaml")


class CameraConfig(BaseModel):
    source: Union[int, str] = Field(0, description="Webcam device ID (0, 1) or RTSP URL / video file path")
    width: int = Field(640, ge=160, le=3840)
    height: int = Field(480, ge=120, le=2160)
    fps_limit: float = Field(15.0, ge=1.0, le=60.0)
    reconnect_interval_s: float = Field(5.0, ge=1.0)


class DetectorConfig(BaseModel):
    backend: str = Field("onnx", description="Detector backend: onnx, synthetic")
    model_path: str = Field("models/yolo11n.onnx")
    confidence_threshold: float = Field(0.50, ge=0.1, le=1.0)
    nms_threshold: float = Field(0.45, ge=0.1, le=1.0)
    input_size: Tuple[int, int] = Field((640, 640))
    target_classes: List[str] = Field(default_factory=lambda: ["person"])


class AppConfig(BaseModel):
    camera: CameraConfig = Field(default_factory=CameraConfig)
    detector: DetectorConfig = Field(default_factory=DetectorConfig)


def load_config(config_path: Optional[Union[str, Path]] = None) -> AppConfig:
    candidates = []
    if config_path:
        candidates.append(Path(config_path))
    if os.environ.get("SENTRY_CONFIG_FILE"):
        candidates.append(Path(os.environ["SENTRY_CONFIG_FILE"]))
    candidates.extend([Path("config.yaml"), Path("config.example.yaml")])

    for p in candidates:
        if p.is_file():
            try:
                import yaml
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                return AppConfig(**data)
            except Exception:
                pass
    return AppConfig()
