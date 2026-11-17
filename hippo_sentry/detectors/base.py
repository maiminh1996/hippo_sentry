from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple
import numpy as np


class DetectionResult:
    """Represents a single detected bounding box and classification."""

    def __init__(
        self,
        class_id: int,
        class_name: str,
        confidence: float,
        bbox: Tuple[float, float, float, float],
    ):
        self.class_id = int(class_id)
        self.class_name = str(class_name)
        self.label = self.class_name  # Convenient alias
        self.confidence = float(confidence)
        self.bbox = tuple(float(v) for v in bbox)  # (x1, y1, x2, y2)

    @property
    def center(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def width(self) -> float:
        return max(0.0, self.bbox[2] - self.bbox[0])

    @property
    def height(self) -> float:
        return max(0.0, self.bbox[3] - self.bbox[1])

    def to_dict(self) -> dict:
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "bbox": [round(c, 1) for c in self.bbox],
            "center": [round(c, 1) for c in self.center],
        }


class BaseDetector(ABC):
    """Abstract base interface for plug-and-play object detection engines."""

    @abstractmethod
    def detect(self, image: np.ndarray) -> List[DetectionResult]:
        """Runs inference on BGR image frame and returns list of detections."""
        pass
