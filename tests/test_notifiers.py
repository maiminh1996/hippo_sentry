import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hippo_sentry.config import TelegramConfig, EmailConfig
from hippo_sentry.notifiers.telegram import TelegramNotifier
from hippo_sentry.notifiers.email_smtp import EmailNotifier


@pytest.mark.asyncio
async def test_telegram_send_alert_mock():
    cfg = TelegramConfig(enabled=True, bot_token="123:TOKEN", chat_id="9999")
    notifier = TelegramNotifier(cfg)
    assert notifier.is_configured is True

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        success = await notifier.send_alert_photo(b"test_jpeg", "Caption")
        assert success is True
        assert mock_post.called


@pytest.mark.asyncio
async def test_email_send_alert_mock():
    cfg = EmailConfig(
        enabled=True,
        smtp_server="smtp.mail.com",
        smtp_port=587,
        sender_email="cam@mail.com",
        sender_password="secret",
        recipient_email="user@mail.com",
    )
    notifier = EmailNotifier(cfg)
    assert notifier.is_configured is True

    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp

    with patch("smtplib.SMTP", return_value=mock_smtp):
        success = await notifier.send_alert(b"test_jpeg", "Subject", "Body")
        assert success is True
