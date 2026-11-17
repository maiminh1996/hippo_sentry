from __future__ import annotations

import json
import logging
from typing import Any, Dict
from ..config import MqttConfig

logger = logging.getLogger(__name__)


class MqttNotifier:
    """Optional MQTT event publisher for smart home integration."""

    def __init__(self, config: MqttConfig):
        self.config = config

    def publish_event(self, payload: Dict[str, Any]) -> bool:
        if not self.config.enabled:
            return False

        try:
            import paho.mqtt.publish as publish
            publish.single(
                topic=self.config.topic,
                payload=json.dumps(payload),
                hostname=self.config.broker_host,
                port=self.config.broker_port,
            )
            logger.info(f"MqttNotifier: Published event to {self.config.topic}")
            return True
        except Exception as exc:
            logger.debug(f"MQTT publish failed: {exc}")
            return False
