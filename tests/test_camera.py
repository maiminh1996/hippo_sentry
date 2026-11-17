import pytest
from hippo_sentry.camera.capture import CameraCapture
from hippo_sentry.config import CameraConfig


def test_camera_synthetic_fallback():
    cfg = CameraConfig(source=999, width=320, height=240)
    cam = CameraCapture(cfg)
    assert cam.is_powered_on is True

    frame = cam.read_frame()
    assert frame is not None
    assert frame.shape == (240, 320, 3)

    # Privacy power toggle
    cam.set_power(False)
    assert cam.is_powered_on is False
    p_frame = cam.read_frame()
    assert p_frame is not None
    assert p_frame.shape == (240, 320, 3)

    cam.release()
