from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from ..config import EmailConfig

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Asynchronous SMTP email alert dispatcher with JPEG attachment."""

    def __init__(self, config: EmailConfig):
        self.config = config

    @property
    def is_configured(self) -> bool:
        return bool(
            self.config.enabled
            and self.config.sender_email
            and self.config.sender_password
            and self.config.recipient_email
        )

    def _send_sync(self, jpeg_bytes: Optional[bytes], subject: str, body: str) -> bool:
        if not self.is_configured:
            return False

        try:
            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = self.config.sender_email
            msg["To"] = self.config.recipient_email

            msg.attach(MIMEText(body, "plain", "utf-8"))

            if jpeg_bytes:
                part = MIMEImage(jpeg_bytes, _subtype="jpeg", name="intruder_snapshot.jpg")
                msg.attach(part)

            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port, timeout=12.0) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.config.sender_email, self.config.sender_password)
                server.send_message(msg)

            logger.info(f"EmailNotifier: Alert delivered to {self.config.recipient_email}.")
            return True
        except Exception as exc:
            logger.error(f"EmailNotifier: Dispatch failed: {exc}")
            return False

    async def send_alert(self, jpeg_bytes: Optional[bytes], subject: str, body: str) -> bool:
        return await asyncio.to_thread(self._send_sync, jpeg_bytes, subject, body)
