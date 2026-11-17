from __future__ import annotations

import math
import time
from typing import List
import numpy as np

from .base import BaseDetector, DetectionResult


class SyntheticDetector(BaseDetector):
    """Mock detector simulating moving targets for testing without GPU/ONNX models."""

    def __init__(self, target_class: str = "person", confidence: float = 0.85):
        self.target_class = target_class
        self.confidence = confidence

    def detect(self, image: np.ndarray) -> List[DetectionResult]:
        if image is None:
            return []

        h, w = image.shape[:2]
        t = time.time()
        cx = w / 2.0 + math.sin(t * 0.8) * (w * 0.25)
        cy = h / 2.0 + math.cos(t * 0.4) * (h * 0.1)

        bw, bh = w * 0.18, h * 0.45
        x1 = max(0.0, cx - bw / 2.0)
        y1 = max(0.0, cy - bh / 2.0)
        x2 = min(float(w), cx + bw / 2.0)
        y2 = min(float(h), cy + bh / 2.0)

        return [
            DetectionResult(
                class_id=0,
                class_name=self.target_class,
                confidence=self.confidence,
                bbox=(x1, y1, x2, y2),
            )
        ]
