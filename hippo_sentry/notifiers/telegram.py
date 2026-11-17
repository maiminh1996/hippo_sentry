from __future__ import annotations

import asyncio
import logging
from typing import Callable, List, Optional
import httpx

from ..config import TelegramConfig

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Bi-directional Telegram Bot interface:
    - Dispatches instant intruder alerts with annotated JPEG photos.
    - Long-polls incoming user commands (/arm, /disarm, /cam on, /cam off, /photo, /status, /help).
    """

    def __init__(self, config: TelegramConfig):
        self.config = config
        self.bot_token = config.bot_token.strip()
        self.chat_id = str(config.chat_id).strip()
        self.allowed_chat_ids = set(str(cid).strip() for cid in config.allowed_chat_ids)
        if self.chat_id:
            self.allowed_chat_ids.add(self.chat_id)

        self._api_base = f"https://api.telegram.org/bot{self.bot_token}"
        self.command_handler: Optional[Callable[[str, str], asyncio.Future]] = None

    @property
    def is_configured(self) -> bool:
        return bool((self.config.enabled or (self.bot_token and self.chat_id)) and self.bot_token and self.chat_id)

    async def send_alert_photo(self, jpeg_bytes: Optional[bytes], caption: str) -> bool:
        """Sends photo alert via Telegram Bot API sendPhoto multipart endpoint."""
        if not self.is_configured:
            return False

        timeout = httpx.Timeout(connect=3.0, read=15.0, write=15.0, pool=5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if jpeg_bytes:
                    url = f"{self._api_base}/sendPhoto"
                    files = {"photo": ("alert_snapshot.jpg", jpeg_bytes, "image/jpeg")}
                    data = {"chat_id": self.chat_id, "caption": caption, "parse_mode": "HTML"}
                    resp = await client.post(url, data=data, files=files)
                else:
                    url = f"{self._api_base}/sendMessage"
                    payload = {"chat_id": self.chat_id, "text": caption, "parse_mode": "HTML"}
                    resp = await client.post(url, json=payload)

                if resp.status_code == 200:
                    logger.info(f"TelegramNotifier: Alert delivered to chat {self.chat_id}.")
                    return True
                else:
                    logger.error(f"TelegramNotifier: API error ({resp.status_code}): {resp.text}")
                    return False
        except Exception as exc:
            logger.error(f"TelegramNotifier: Delivery failed: {exc}")
            return False

    async def send_text_message(self, text: str, target_chat_id: Optional[str] = None) -> bool:
        """Sends text reply to user."""
        if not self.config.enabled or not self.bot_token:
            return False

        cid = target_chat_id or self.chat_id
        if not cid:
            return False

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{self._api_base}/sendMessage",
                    json={"chat_id": cid, "text": text, "parse_mode": "HTML"},
                )
                return resp.status_code == 200
        except Exception as exc:
            logger.debug(f"Telegram send message error: {exc}")
            return False

    async def poll_commands_loop(self, is_running_callback: Callable[[], bool]) -> None:
        """Background long-polling loop receiving remote interactive bot commands."""
        if not self.config.enabled or not self.bot_token:
            return

        logger.info("TelegramNotifier: Command listener active.")
        offset = 0

        while is_running_callback():
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        f"{self._api_base}/getUpdates",
                        params={"offset": offset, "timeout": 2},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for update in data.get("result", []):
                            offset = update.get("update_id", offset) + 1
                            msg = update.get("message", {})
                            text = (msg.get("text") or "").strip()
                            chat_id = str(msg.get("chat", {}).get("id", ""))

                            # Security whitelist check
                            if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
                                logger.warning(f"TelegramNotifier: Rejected unauthorized command from {chat_id}")
                                continue

                            if text and self.command_handler:
                                await self.command_handler(text, chat_id)
            except Exception as exc:
                logger.debug(f"Telegram polling exception: {exc}")

            await asyncio.sleep(self.config.polling_interval_seconds)
