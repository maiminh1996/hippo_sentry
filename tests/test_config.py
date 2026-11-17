import pytest
from hippo_sentry.config import AppConfig, load_config


def test_default_config_schema():
    cfg = AppConfig()
    assert cfg.camera.width == 640
    assert cfg.camera.height == 480
    assert cfg.detector.backend == "onnx"
    assert "person" in cfg.detector.target_classes
    assert cfg.sentry.cooldown_seconds == 60
    assert cfg.telegram.enabled is False
    assert cfg.email.enabled is False
    assert cfg.web.port == 8080


def test_load_config_fallback(tmp_path):
    p = tmp_path / "nonexistent.yaml"
    cfg = load_config(p)
    assert isinstance(cfg, AppConfig)
