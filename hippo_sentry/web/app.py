from __future__ import annotations

import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

from ..core import SentryEngine

STATIC_DIR = Path(__file__).resolve().parent / "static"


class SentryToggleRequest(BaseModel):
    enabled: bool | None = None


def create_web_app(engine: SentryEngine) -> FastAPI:
    app = FastAPI(title="Smart Sentry Vision", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/hippo_icon.png")
    async def serve_hippo_icon():
        candidates = [
            STATIC_DIR / "hippo_icon.png",
            Path(__file__).resolve().parent / "static" / "hippo_icon.png",
            Path("hippo_icon.png"),
            Path("/app/hippo_icon.png"),
            Path(__file__).resolve().parent.parent.parent / "hippo_icon.png",
        ]
        for cp in candidates:
            if cp.is_file():
                return FileResponse(cp, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
        return Response(status_code=404)

    @app.get("/")
    async def serve_dashboard():
        index_file = STATIC_DIR / "index.html"
        if index_file.is_file():
            headers = {
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }
            return FileResponse(index_file, headers=headers)
        return {"status": "ok", "message": "Smart Sentry Vision API"}

    @app.get("/api/status")
    async def get_status():
        return engine.get_status()

    @app.post("/api/arm")
    async def arm_sentry():
        return {"status": "SUCCESS", "armed": engine.arm()}

    @app.post("/api/disarm")
    async def disarm_sentry():
        return {"status": "SUCCESS", "armed": engine.disarm()}

    @app.post("/api/camera/toggle")
    async def toggle_camera(req: SentryToggleRequest = None):
        val = req.enabled if req else None
        return {"status": "SUCCESS", "camera_power": engine.toggle_camera(val)}

    @app.post("/api/alert/test")
    async def trigger_test_alert():
        frame, _ = await engine.process_frame()
        jpeg = engine._encode_jpeg(frame)
        res = await engine.dispatch_alert(jpeg, None)
        return {"status": "SUCCESS", "result": res}

    @app.get("/video/snapshot")
    async def get_snapshot():
        jpeg = engine.get_latest_jpeg()
        if not jpeg:
            frame, _ = await engine.process_frame()
            jpeg = engine._encode_jpeg(frame)
        return Response(content=jpeg or b"", media_type="image/jpeg")

    @app.get("/video/stream")
    async def video_stream():
        async def _generator():
            while True:
                try:
                    jpeg = engine.get_latest_jpeg()
                    if jpeg:
                        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
                except Exception:
                    pass
                await asyncio.sleep(0.06)

        return StreamingResponse(_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

    return app
