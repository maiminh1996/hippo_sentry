from __future__ import annotations

import logging
import math
import os
import threading
import time
from typing import Optional, Tuple, Union
import numpy as np

from ..config import CameraConfig

try:
    import cv2
except ImportError:
    cv2 = None

logger = logging.getLogger(__name__)


class CameraCapture:
    """
    Thread-safe camera frame grabber supporting V4L2 webcams, RTSP streams,
    video files, and privacy-shield mode.
    """

    def __init__(self, config: CameraConfig):
        self.source = config.source
        self.width = config.width
        self.height = config.height
        self.fps_limit = config.fps_limit
        self.reconnect_interval_s = config.reconnect_interval_s

        self.is_powered_on: bool = True
        self.has_physical_device: bool = False
        self.measured_fps: float = 0.0

        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.RLock()
        self._last_frame_time: float = 0.0
        self._last_init_time: float = 0.0

        self._init_camera()

    def _init_camera(self) -> None:
        if cv2 is None:
            logger.warning("OpenCV not installed; camera capture operating in synthetic fallback mode.")
            return

        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None

            logger.info(f"CameraCapture: Connecting to source: {self.source}...")
            cap = None
            if isinstance(self.source, int):
                # USB Webcam
                dev_path = f"/dev/video{self.source}"
                if os.path.exists(dev_path) or os.name == "nt":
                    cap = cv2.VideoCapture(self.source)
            else:
                # RTSP / HTTP / file string
                cap = cv2.VideoCapture(str(self.source))

            if cap is not None and cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self._cap = cap
                self.has_physical_device = True
                logger.info(f"CameraCapture: Device online ({self.width}x{self.height}).")
            else:
                self.has_physical_device = False
                logger.warning(f"CameraCapture: Could not open {self.source}. Using synthetic animated feed.")

    def set_power(self, enabled: bool) -> bool:
        """Toggle camera sensor capture on/off (Privacy mode)."""
        with self._lock:
            self.is_powered_on = enabled
            logger.info(f"CameraCapture: Sensor power state changed to: {'ON' if enabled else 'OFF (Privacy Shield)'}")
            return self.is_powered_on

    def read_frame(self) -> Optional[np.ndarray]:
        """Reads next frame, respecting power state and frame rate throttle."""
        if not self.is_powered_on:
            return self._generate_privacy_frame()

        now = time.time()
        with self._lock:
            # Reconnect check
            if not self.has_physical_device and (now - self._last_init_time > self.reconnect_interval_s):
                self._last_init_time = now
                self._init_camera()

            if self.has_physical_device and self._cap is not None:
                try:
                    ret, frame = self._cap.read()
                    if ret and frame is not None:
                        self._update_fps(now)
                        return frame
                except Exception as exc:
                    logger.debug(f"Camera read exception: {exc}")

        # Fallback to animated synthetic test feed
        self._update_fps(now)
        return self._generate_synthetic_frame(now)

    def _update_fps(self, now: float) -> None:
        dt = now - self._last_frame_time
        self._last_frame_time = now
        if dt > 0:
            inst_fps = 1.0 / dt
            self.measured_fps = round(self.measured_fps * 0.85 + inst_fps * 0.15, 1) if self.measured_fps > 0 else round(inst_fps, 1)

    def _generate_synthetic_frame(self, t: float) -> Optional[np.ndarray]:
        if cv2 is None or np is None:
            return None

        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = (32, 24, 18)

        # Draw grid
        for y in range(0, self.height, 40):
            cv2.line(frame, (0, y), (self.width, y), (42, 34, 28), 1)
        for x in range(0, self.width, 40):
            cv2.line(frame, (x, 0), (x, self.height), (42, 34, 28), 1)

        # Draw simulated human figure moving across view
        sx = int(self.width / 2.0 + math.sin(t * 0.8) * (self.width * 0.22))
        sy = int(self.height / 2.0 + math.cos(t * 0.4) * (self.height * 0.08))

        cv2.circle(frame, (sx, sy - 45), 20, (180, 140, 100), -1)
        cv2.rectangle(frame, (sx - 24, sy - 22), (sx + 24, sy + 75), (220, 160, 60), -1)

        cv2.putText(frame, "[SYNTHETIC CAMERA FEED - NO DEVICE]", (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)
        return frame

    def _generate_privacy_frame(self) -> Optional[np.ndarray]:
        if cv2 is None or np is None:
            return None

        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = (18, 18, 18)

        cx, cy = self.width // 2, self.height // 2
        cv2.putText(frame, "CAMERA SENSOR DISABLED", (cx - 140, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.putText(frame, "Privacy mode active", (cx - 80, cy + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (130, 130, 130), 1, cv2.LINE_AA)
        return frame

    def release(self) -> None:
        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
