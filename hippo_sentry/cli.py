from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uvicorn

from .config import load_config
from .core import SentryEngine
from .web.app import create_web_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("hippo-sentry")


def find_telegram_chat_id(token: str) -> None:
    """Helper to discover user chat_id from Telegram getUpdates."""
    import httpx
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    print(f"Querying Telegram API for bot token: {token[:8]}***...")
    try:
        resp = httpx.get(url, timeout=10.0)
        data = resp.json()
        if not data.get("ok"):
            print(f"Error: {data.get('description')}")
            return

        results = data.get("result", [])
        if not results:
            print("No messages found! Please open Telegram, search your bot, and press START or send 'hello', then rerun.")
            return

        last = results[-1]
        msg = last.get("message") or last.get("channel_post") or {}
        chat = msg.get("chat", {})
        cid = chat.get("id") or msg.get("from", {}).get("id")
        user = chat.get("username") or msg.get("from", {}).get("username") or "unknown"
        print("=" * 60)
        print(f" SUCCESS: Found Telegram Chat ID: {cid} (User: @{user})")
        print(f" Paste this into your config.yaml under telegram.chat_id: '{cid}'")
        print("=" * 60)
    except Exception as exc:
        print(f"Failed to query Telegram API: {exc}")


async def run_server(config_path: str) -> None:
    cfg = load_config(config_path)
    engine = SentryEngine(cfg)
    await engine.start()

    if cfg.web.enabled:
        app = create_web_app(engine)
        uv_config = uvicorn.Config(app, host=cfg.web.host, port=cfg.web.port, log_level="warning")
        server = uvicorn.Server(uv_config)
        try:
            await server.serve()
        finally:
            await engine.stop()
    else:
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            await engine.stop()


def main():
    parser = argparse.ArgumentParser(description="Hippo Sentry Vision - Modular Edge Camera Surveillance Engine")
    subparsers = parser.add_subparsers(dest="command")

    run_p = subparsers.add_parser("run", help="Start Sentry monitoring engine and web server")
    run_p.add_argument("--config", "-c", default="config.yaml", help="Path to config.yaml")

    tg_p = subparsers.add_parser("find-chat-id", help="Auto-detect your Telegram Chat ID")
    tg_p.add_argument("--token", "-t", required=True, help="Telegram Bot Token from @BotFather")

    args = parser.parse_args()

    if args.command == "find-chat-id":
        find_telegram_chat_id(args.token)
    elif args.command == "run" or args.command is None:
        cfg_file = getattr(args, "config", "config.yaml")
        try:
            asyncio.run(run_server(cfg_file))
        except KeyboardInterrupt:
            print("\nExiting Smart Sentry Vision.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
