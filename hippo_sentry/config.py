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


class SentryWatchdogConfig(BaseModel):
    enabled: bool = False
    cooldown_seconds: int = Field(60, ge=1)
    draw_boxes: bool = True
    save_local_snapshots: bool = True
    snapshot_dir: str = "snapshots"


class TelegramConfig(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""
    allowed_chat_ids: List[str] = Field(default_factory=list)
    polling_interval_seconds: float = Field(2.0, ge=0.5)


class EmailConfig(BaseModel):
    enabled: bool = False
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    sender_email: str = ""
    sender_password: str = ""
    recipient_email: str = ""


class MqttConfig(BaseModel):
    enabled: bool = False
    broker_host: str = "localhost"
    broker_port: int = 1883
    topic: str = "sentry/events/intrusion"


class WebConfig(BaseModel):
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080


class AppConfig(BaseModel):
    camera: CameraConfig = Field(default_factory=CameraConfig)
    detector: DetectorConfig = Field(default_factory=DetectorConfig)
    sentry: SentryWatchdogConfig = Field(default_factory=SentryWatchdogConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    mqtt: MqttConfig = Field(default_factory=MqttConfig)
    web: WebConfig = Field(default_factory=WebConfig)


def load_config(config_path: Optional[Union[str, Path]] = None) -> AppConfig:
    candidates = []
    if config_path:
        candidates.append(Path(config_path))
    if os.environ.get("SENTRY_CONFIG_FILE"):
        candidates.append(Path(os.environ["SENTRY_CONFIG_FILE"]))
    candidates.extend([Path("config.yaml"), Path("/app/config.yaml"), Path("config.example.yaml"), Path("/app/config.example.yaml")])

    for p in candidates:
        if p.is_file():
            try:
                import yaml
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                cfg = AppConfig(**data)
                # Auto-enable telegram if user provided credentials
                if cfg.telegram.bot_token and cfg.telegram.chat_id and not cfg.telegram.enabled:
                    cfg.telegram.enabled = True
                return cfg
            except Exception as exc:
                print(f"Warning: Failed to parse {p} ({exc}), checking next.")
    return AppConfig()
