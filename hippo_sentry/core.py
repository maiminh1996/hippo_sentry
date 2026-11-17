from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from .config import AppConfig
from .camera.capture import CameraCapture
from .detectors.base import BaseDetector, DetectionResult
from .detectors.factory import create_detector
from .notifiers.telegram import TelegramNotifier
from .notifiers.email_smtp import EmailNotifier
from .notifiers.mqtt_pub import MqttNotifier
from .system import SystemMonitor

try:
    import cv2
except ImportError:
    cv2 = None

logger = logging.getLogger(__name__)


class SentryEngine:
    """
    Central Sentry Engine coordinating:
    - Real-time camera capture & privacy mode toggle.
    - Modular, pluggable object detection inference.
    - Sentry intrusion detection with anti-spam cooldown.
    - Bi-directional Telegram Bot commands & SMTP email notifications.
    """

    def __init__(self, config: AppConfig):
        self.config = config

        self.camera = CameraCapture(config.camera)
        self.detector = create_detector(config.detector)

        self.telegram = TelegramNotifier(config.telegram)
        self.telegram.command_handler = self._handle_telegram_command

        self.email = EmailNotifier(config.email)
        self.mqtt = MqttNotifier(config.mqtt)
        self.system_monitor = SystemMonitor()

        self.is_armed: bool = config.sentry.enabled
        self.alerts_count: int = 0
        self.last_alert_time: float = 0.0
        self.last_detections: List[DetectionResult] = []

        self._running: bool = False
        self._background_tasks: List[asyncio.Task] = []
        self._latest_jpeg: Optional[bytes] = None
        self._latest_annotated: Optional[np.ndarray] = None

    async def start(self) -> None:
        logger.info("Starting SentryEngine...")
        self._running = True

        self._background_tasks = [
            asyncio.create_task(self._vision_loop(), name="sentry_vision_loop"),
        ]
        if (self.telegram.config.enabled or (self.telegram.bot_token and self.telegram.chat_id)) and self.telegram.bot_token:
            self._background_tasks.append(
                asyncio.create_task(self.telegram.poll_commands_loop(lambda: self._running), name="telegram_listener")
            )
        logger.info(f"SentryEngine online. Sentry status: {"ARMED" if self.is_armed else "DISARMED"}")

    async def stop(self) -> None:
        logger.info("Stopping SentryEngine...")
        self._running = False
        for t in self._background_tasks:
            t.cancel()
        self.camera.release()

    def arm(self) -> bool:
        if not self.camera.is_powered_on:
            self.camera.set_power(True)
            logger.info("SentryEngine: Camera enabled automatically upon arming guard.")
        self.is_armed = True
        logger.info("SentryEngine: ARMED.")
        return True

    def disarm(self) -> bool:
        self.is_armed = False
        logger.info("SentryEngine: DISARMED.")
        return False

    def toggle_camera(self, enabled: Optional[bool] = None) -> bool:
        new_state = (not self.camera.is_powered_on) if enabled is None else enabled
        is_on = self.camera.set_power(new_state)
        if not is_on and self.is_armed:
            self.disarm()
            logger.info("SentryEngine: Camera disabled -> Guard mode automatically DISARMED.")
        return is_on

    def get_latest_jpeg(self) -> Optional[bytes]:
        return self._latest_jpeg

    async def process_frame(self) -> Tuple[Optional[np.ndarray], List[DetectionResult]]:
        frame = await asyncio.to_thread(self.camera.read_frame)
        if frame is None:
            return None, []

        # If camera sensor is powered off, skip detection
        if not self.camera.is_powered_on:
            self.last_detections = []
            return frame, []

        # If guard is disarmed, skip neural network inference to keep CPU near 1%
        if not self.is_armed:
            self.last_detections = []
            return frame, []

        detections = await asyncio.to_thread(self.detector.detect, frame)
        self.last_detections = detections

        annotated = frame.copy()
        if cv2 is not None and self.config.sentry.draw_boxes:
            for det in detections:
                x1, y1, x2, y2 = [int(v) for v in det.bbox]
                color = (0, 255, 128) if det.class_name == "person" else (255, 180, 0)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    annotated,
                    f"{det.class_name} {det.confidence:.2f}",
                    (x1, max(15, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                )

        return annotated, detections

    async def _vision_loop(self) -> None:
        last_logged_det_time = 0.0
        while self._running:
            try:
                if not self.camera.is_powered_on:
                    p_frame = await asyncio.to_thread(self.camera.read_frame)
                    self._latest_jpeg = self._encode_jpeg(p_frame)
                    self.last_detections = []
                    await asyncio.sleep(0.25)
                    continue

                frame, detections = await self.process_frame()
                self._latest_annotated = frame
                self._latest_jpeg = self._encode_jpeg(frame)

                if self.is_armed and detections:
                    now = time.time()
                    if now - last_logged_det_time >= 1.5:
                        last_logged_det_time = now
                        det_str = ", ".join(f"{d.class_name}:{d.confidence*100:.0f}%" for d in detections)
                        logger.info(f"Target detected: {det_str}")

                    for det in detections:
                        if now - self.last_alert_time >= self.config.sentry.cooldown_seconds:
                            self.last_alert_time = now
                            self.alerts_count += 1
                            logger.warning(f"INTRUDER ALERT DISPATCHED: {det.class_name} ({det.confidence*100:.1f}%)")

                            jpeg_bytes = self._latest_jpeg
                            if self.config.sentry.save_local_snapshots and jpeg_bytes:
                                self._save_local_snapshot(jpeg_bytes)

                            asyncio.create_task(self.dispatch_alert(jpeg_bytes, det))
                            break
            except Exception as exc:
                logger.debug(f"Vision loop exception: {exc}")

            await asyncio.sleep(1.0 / self.config.camera.fps_limit)

    def _encode_jpeg(self, frame: Optional[np.ndarray]) -> Optional[bytes]:
        if cv2 is None or frame is None:
            return None
        try:
            ret, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return buf.tobytes() if ret else None
        except Exception:
            return None

    def _save_local_snapshot(self, jpeg_bytes: bytes) -> None:
        try:
            snap_dir = Path(self.config.sentry.snapshot_dir)
            snap_dir.mkdir(parents=True, exist_ok=True)
            fname = snap_dir / f"intruder_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
            fname.write_bytes(jpeg_bytes)
        except Exception as exc:
            logger.debug(f"Save snapshot failed: {exc}")

    async def dispatch_alert(self, jpeg_bytes: Optional[bytes], det: Optional[DetectionResult] = None) -> Dict[str, Any]:
        time_str = time.strftime("%Y-%m-%d %H:%M:%S")
        label = det.class_name if det else "Target"
        conf = round((det.confidence * 100) if det else 99.0, 1)

        tg_caption = (
            f"<b>[SENTRY ALERT] Intrusion Detected</b>\n\n"
            f"Time: {time_str}\n"
            f"Target: {label} ({conf}% confidence)\n"
            f"Status: Monitored area breached"
        )

        email_sub = f"[SENTRY ALERT] {label} detected ({conf}%) at {time_str}"
        email_body = f"Intruder detected at {time_str}. Classification: {label} ({conf}%). Snapshot attached."

        tasks = []
        if self.telegram.is_configured:
            tasks.append(self.telegram.send_alert_photo(jpeg_bytes, tg_caption))
        if self.email.is_configured:
            tasks.append(self.email.send_alert(jpeg_bytes, email_sub, email_body))

        results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []
        self.mqtt.publish_event({"event": "intrusion", "time": time_str, "label": label, "confidence": conf})

        return {
            "status": "DISPATCHED",
            "time": time_str,
            "label": label,
            "confidence": conf,
            "results_count": len(results),
        }

    async def _handle_telegram_command(self, text: str, chat_id: str) -> None:
        cmd = text.strip().lower()

        if cmd in ("/arm", "/guard", "arm"):
            self.arm()
            await self.telegram.send_text_message("<b>Sentry Guard Mode: ARMED</b>\nMonitoring active.", chat_id)

        elif cmd in ("/disarm", "disarm"):
            self.disarm()
            await self.telegram.send_text_message("<b>Sentry Guard Mode: DISARMED</b>", chat_id)

        elif cmd in ("/cam_on", "/camera_on", "cam_on", "camera_on", "/cam on", "/camera on", "cam on"):
            self.toggle_camera(True)
            await self.telegram.send_text_message("<b>Camera Hardware: ON</b>\nSensor capture active.", chat_id)

        elif cmd in ("/cam_off", "/camera_off", "/privacy", "cam_off", "camera_off", "/cam off", "/camera off", "cam off"):
            self.toggle_camera(False)
            await self.telegram.send_text_message("<b>Privacy Mode: ACTIVE</b>\nCamera sensor powered off.", chat_id)

        elif cmd in ("/photo", "/snapshot", "photo", "camera"):
            frame, _ = await self.process_frame()
            jpeg = self._encode_jpeg(frame)
            await self.telegram.send_alert_photo(jpeg, f"<b>Camera Snapshot</b> ({time.strftime('%H:%M:%S')})")

        elif cmd in ("/status", "status"):
            arm_str = "ARMED" if self.is_armed else "WAITING"
            cam_str = "ONLINE" if self.camera.is_powered_on else "OFF (Privacy)"
            fps = self.camera.measured_fps
            targets = len(self.last_detections)
            sys_m = self.system_monitor.get_metrics()
            msg = (
                f"<b>System Status</b>\n\n"
                f"- Guard Mode: {arm_str}\n"
                f"- Camera State: {cam_str}\n"
                f"- Frame Rate: {fps} FPS\n"
                f"- CPU: {sys_m['cpu_percent']}%\n"
                f"- RAM: {int(sys_m['app_ram_mb'])} MB / {sys_m['host_ram_gb']} GB\n"
                f"- Active Targets: {targets}\n"
                f"- Alerts Dispatched: {self.alerts_count}"
            )
            await self.telegram.send_text_message(msg, chat_id)

        elif cmd in ("/help", "/start", "help"):
            help_text = (
                "<b>Sentry Camera System Commands:</b>\n\n"
                "/arm - Arm intrusion detection\n"
                "/disarm - Disarm guard mode\n"
                "/cam_on - Power on camera sensor\n"
                "/cam_off - Power off camera (Privacy mode)\n"
                "/photo - Capture live photo snapshot\n"
                "/status - Report system telemetry and FPS\n"
                "/help - Display command reference"
            )
            await self.telegram.send_text_message(help_text, chat_id)

    def get_status(self) -> dict:
        return {
            "armed": self.is_armed,
            "camera_power": self.camera.is_powered_on,
            "has_physical_device": self.camera.has_physical_device,
            "fps": self.camera.measured_fps,
            "alerts_count": self.alerts_count,
            "last_alert_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_alert_time)) if self.last_alert_time > 0 else "None",
            "active_detections": [d.to_dict() for d in self.last_detections],
            "target_classes": self.config.detector.target_classes,
            "channels": {
                "telegram": self.telegram.is_configured,
                "email": self.email.is_configured,
                "mqtt": self.mqtt.config.enabled,
            },
            "system": self.system_monitor.get_metrics(),
        }
