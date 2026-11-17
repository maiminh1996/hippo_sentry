import numpy as np
import pytest
from hippo_sentry.detectors.base import DetectionResult
from hippo_sentry.detectors.synthetic import SyntheticDetector
from hippo_sentry.detectors.factory import create_detector
from hippo_sentry.config import DetectorConfig


def test_detection_result_properties():
    d = DetectionResult(class_id=0, class_name="person", confidence=0.88, bbox=(10.0, 20.0, 110.0, 220.0))
    assert d.class_name == "person"
    assert d.label == "person"
    assert d.width == 100.0
    assert d.height == 200.0
    assert d.center == (60.0, 120.0)
    dct = d.to_dict()
    assert dct["confidence"] == 0.88


def test_synthetic_detector():
    det = SyntheticDetector(target_class="person", confidence=0.90)
    fake_img = np.zeros((480, 640, 3), dtype=np.uint8)
    results = det.detect(fake_img)
    assert len(results) == 1
    assert results[0].class_name == "person"
    assert results[0].confidence == 0.90


def test_detector_factory():
    cfg = DetectorConfig(backend="synthetic")
    d = create_detector(cfg)
    assert isinstance(d, SyntheticDetector)
