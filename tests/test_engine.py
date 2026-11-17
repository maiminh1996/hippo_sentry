import pytest
from hippo_sentry.config import AppConfig, DetectorConfig, SentryWatchdogConfig
from hippo_sentry.core import SentryEngine


@pytest.mark.asyncio
async def test_engine_arm_disarm_and_process():
    cfg = AppConfig(
        detector=DetectorConfig(backend="synthetic"),
        sentry=SentryWatchdogConfig(enabled=False, cooldown_seconds=1),
    )
    engine = SentryEngine(cfg)
    assert engine.is_armed is False

    engine.arm()
    assert engine.is_armed is True

    frame, detections = await engine.process_frame()
    assert frame is not None
    assert len(detections) >= 1

    engine.disarm()
    assert engine.is_armed is False

    status = engine.get_status()
    assert status["armed"] is False
    assert "channels" in status
    assert "system" in status
    assert "cpu_percent" in status["system"]
    assert "app_ram_mb" in status["system"]
    assert "host_ram_gb" in status["system"]

    # Test motion gate toggle
    assert engine.config.sentry.motion_gate_enabled is True
    assert engine.toggle_motion_gate(False) is False
    assert engine.config.sentry.motion_gate_enabled is False
    assert engine.toggle_motion_gate(True) is True

    engine.camera.release()
