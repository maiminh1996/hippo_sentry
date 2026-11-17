import numpy as np
from hippo_sentry.detectors.motion import MotionGate


def test_motion_gate_detection():
    gate = MotionGate(min_area_ratio=0.015, persistence_frames=2)

    # Frame 1: Warmup baseline
    f1 = np.zeros((240, 320, 3), dtype=np.uint8)
    assert gate.check_motion(f1) is True

    # Frame 2: Identical frame (empty room, zero movement) -> False
    f2 = np.zeros((240, 320, 3), dtype=np.uint8)
    assert gate.check_motion(f2) is False

    # Frame 3: Significant movement (intruder entering) -> True
    f3 = f2.copy()
    f3[50:180, 50:180] = 255
    assert gate.check_motion(f3) is True

    # Test reset
    gate.reset()
    assert gate._prev_gray is None
