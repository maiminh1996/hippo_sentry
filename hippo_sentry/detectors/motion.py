"""Two-stage motion gating filter using fast frame differencing."""

from __future__ import annotations

import logging
from typing import Optional
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

logger = logging.getLogger(__name__)


class MotionGate:
    """
    Stage 1 motion gate:
    Evaluates frame differencing at a downscaled resolution in < 0.2ms.
    If the room is static, returns False so YOLOv11 deep neural network inference can be skipped.
    """

    def __init__(
        self,
        min_area_ratio: float = 0.015,
        threshold: int = 25,
        persistence_frames: int = 15,
    ) -> None:
        self.min_area_ratio = min_area_ratio
        self.threshold = threshold
        self.persistence_frames = persistence_frames

        self._prev_gray: Optional[np.ndarray] = None
        self._persistence_counter: int = 0

    def check_motion(self, frame: Optional[np.ndarray]) -> bool:
        """Returns True if significant pixel change is detected or within persistence window."""
        if frame is None or cv2 is None or np is None:
            return True

        try:
            # Downscale to 160x120 for 0.1ms processing
            small = cv2.resize(frame, (160, 120), interpolation=cv2.INTER_LINEAR)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if self._prev_gray is None:
                self._prev_gray = gray
                return True

            # Compute absolute difference against previous frame
            diff = cv2.absdiff(self._prev_gray, gray)
            self._prev_gray = gray

            # Threshold and calculate changed pixel ratio
            _, thresh = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)
            changed_pixels = cv2.countNonZero(thresh)
            ratio = changed_pixels / (160.0 * 120.0)

            if ratio >= self.min_area_ratio:
                self._persistence_counter = self.persistence_frames
                return True

            if self._persistence_counter > 0:
                self._persistence_counter -= 1
                return True

            return False
        except Exception as exc:
            logger.debug(f"Motion gate error: {exc}")
            return True

    def reset(self) -> None:
        """Resets previous frame baseline."""
        self._prev_gray = None
        self._persistence_counter = 0
