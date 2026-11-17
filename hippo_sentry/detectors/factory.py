from __future__ import annotations

import logging
from .base import BaseDetector
from .onnx_yolo import ONNXYOLODetector
from .synthetic import SyntheticDetector
from ..config import DetectorConfig

logger = logging.getLogger(__name__)


def create_detector(cfg: DetectorConfig) -> BaseDetector:
    """Factory instantiating requested detection backend."""
    backend = (cfg.backend or "onnx").lower()
    if backend == "synthetic":
        logger.info("Initializing Synthetic mock detector.")
        return SyntheticDetector(
            target_class=cfg.target_classes[0] if cfg.target_classes else "person",
            confidence=0.88,
        )

    logger.info(f"Initializing ONNXYOLODetector with model: {cfg.model_path}")
    return ONNXYOLODetector(
        model_path=cfg.model_path,
        confidence_threshold=cfg.confidence_threshold,
        nms_threshold=cfg.nms_threshold,
        input_size=cfg.input_size,
        target_classes=cfg.target_classes,
    )
