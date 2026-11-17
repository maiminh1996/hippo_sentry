from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np

from .base import BaseDetector, DetectionResult

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import onnxruntime as ort
except ImportError:
    ort = None

logger = logging.getLogger(__name__)

COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator",
    "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
]


class ONNXYOLODetector(BaseDetector):
    """
    Universal ONNX Runtime inference engine supporting YOLOv11, YOLOv8, and YOLOv5 models.
    Supports letterbox pre-processing, custom NMS, and class filtering.
    """

    def __init__(
        self,
        model_path: str | Path,
        confidence_threshold: float = 0.50,
        nms_threshold: float = 0.45,
        input_size: Tuple[int, int] = (640, 640),
        target_classes: Optional[List[str]] = None,
        class_names: Optional[List[str]] = None,
    ):
        self.model_path = Path(model_path)
        self.conf_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.input_size = input_size
        self.target_classes = set(c.lower() for c in (target_classes or ["person"]))
        self.class_names = class_names or COCO_CLASSES

        self.session: Optional[ort.InferenceSession] = None
        self._input_name: Optional[str] = None
        self._init_session()

    def _init_session(self) -> None:
        if ort is None:
            logger.warning("ONNXYOLODetector: onnxruntime not installed. Detection disabled.")
            return

        if not self.model_path.is_file():
            logger.warning(f"ONNXYOLODetector: Model file not found at '{self.model_path}'. Run scripts/download_models.sh.")
            return

        try:
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 4
            self.session = ort.InferenceSession(
                str(self.model_path), sess_options=opts, providers=["CPUExecutionProvider"]
            )
            self._input_name = self.session.get_inputs()[0].name
            logger.info(f"ONNXYOLODetector: Successfully initialized ONNX model from {self.model_path}")
        except Exception as exc:
            logger.error(f"ONNXYOLODetector initialization error: {exc}")

    def detect(self, image: np.ndarray) -> List[DetectionResult]:
        if self.session is None or image is None or cv2 is None:
            return []

        orig_h, orig_w = image.shape[:2]
        blob, scale, pad_w, pad_h = self._preprocess(image)

        try:
            outputs = self.session.run(None, {self._input_name: blob})
            raw_output = outputs[0]  # shape: (1, 84, 8400) for YOLOv8/11 or (1, 8400, 84)
            return self._postprocess(raw_output, orig_w, orig_h, scale, pad_w, pad_h)
        except Exception as exc:
            logger.debug(f"Inference error: {exc}")
            return []

    def _preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, float, float, float]:
        target_w, target_h = self.input_size
        orig_h, orig_w = image.shape[:2]

        scale = min(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)

        pad_w = (target_w - new_w) // 2
        pad_h = (target_h - new_h) // 2
        canvas[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized

        blob = cv2.dnn.blobFromImage(canvas, 1.0 / 255.0, (target_w, target_h), swapRB=True, crop=False)
        return blob, scale, float(pad_w), float(pad_h)

    def _postprocess(
        self,
        raw: np.ndarray,
        orig_w: int,
        orig_h: int,
        scale: float,
        pad_w: float,
        pad_h: float,
    ) -> List[DetectionResult]:
        # Handle shape transpose if (1, 84, N) -> (N, 84)
        pred = raw[0]
        if pred.shape[0] < pred.shape[1]:
            pred = pred.T

        boxes = []
        confidences = []
        class_ids = []

        num_classes = len(self.class_names)
        for row in pred:
            class_scores = row[4 : 4 + num_classes]
            cls_id = int(np.argmax(class_scores))
            conf = float(class_scores[cls_id])

            if conf >= self.conf_threshold:
                c_name = self.class_names[cls_id] if cls_id < len(self.class_names) else f"class_{cls_id}"
                if self.target_classes and c_name.lower() not in self.target_classes:
                    continue

                cx, cy, w, h = row[0], row[1], row[2], row[3]
                x1 = (cx - w / 2.0 - pad_w) / scale
                y1 = (cy - h / 2.0 - pad_h) / scale
                x2 = (cx + w / 2.0 - pad_w) / scale
                y2 = (cy + h / 2.0 - pad_h) / scale

                x1 = max(0.0, min(float(orig_w), x1))
                y1 = max(0.0, min(float(orig_h), y1))
                x2 = max(0.0, min(float(orig_w), x2))
                y2 = max(0.0, min(float(orig_h), y2))

                boxes.append([int(x1), int(y1), int(x2 - x1), int(y2 - y1)])
                confidences.append(conf)
                class_ids.append(cls_id)

        if not boxes:
            return []

        indices = cv2.dnn.NMSBoxes(boxes, confidences, self.conf_threshold, self.nms_threshold)
        results = []
        if len(indices) > 0:
            for idx in indices.flatten():
                bx, by, bw, bh = boxes[idx]
                cid = class_ids[idx]
                cname = self.class_names[cid] if cid < len(self.class_names) else f"class_{cid}"
                results.append(
                    DetectionResult(
                        class_id=cid,
                        class_name=cname,
                        confidence=confidences[idx],
                        bbox=(float(bx), float(by), float(bx + bw), float(by + bh)),
                    )
                )
        return results
