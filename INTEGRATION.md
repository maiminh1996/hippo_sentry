# Integration Reference

How to hook Hippo Sentry into other services, scripts, or home automation systems.

## 1. MQTT Event Hook

Set `mqtt.enabled: true` in `config.yaml` to publish JSON events whenever an intruder is detected.

Topic: `sentry/events/intrusion`

Payload example:
```json
{
  "event": "intrusion",
  "label": "person",
  "confidence": 88.5,
  "time": "2026-11-17 14:20:00"
}
```

Python subscriber example:
```python
import json
import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode())
    print(f"Intruder detected: {data['label']} ({data['confidence']}%)")

client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("sentry/events/intrusion")
client.loop_forever()
```

## 2. HTTP Endpoints

Useful for triggering guard mode from scripts or webhooks:

- `POST /api/arm` — Arms detection watchdog
- `POST /api/disarm` — Disarms detection (drops CPU to idle)
- `POST /api/camera/toggle` — Toggles camera sensor on/off (privacy mode)
- `GET /api/status` — Returns JSON with telemetry, CPU/RAM, and detections
- `GET /video/snapshot` — Returns latest JPEG frame

Example arming with curl:
```bash
curl -X POST http://localhost:8080/api/arm
```

## 3. Sharing the Camera Stream (MJPEG)

Linux V4L2 webcams (`/dev/video0`) can only be opened by one process at a time. If you have another script or service that needs camera access, let Hippo Sentry hold the hardware device and read the stream over HTTP:

Stream URL: `http://localhost:8080/video/stream`

OpenCV consumer:
```python
import cv2

cap = cv2.VideoCapture("http://localhost:8080/video/stream")
while True:
    ret, frame = cap.read()
    if ret:
        cv2.imshow("Stream", frame)
        if cv2.waitKey(1) == 27:
            break
```

## 4. Python Import

If you want to run the engine directly inside your own Python code:

```python
import asyncio
from smart_sentry import SentryEngine, load_config

async def main():
    engine = SentryEngine(load_config("config.yaml"))
    engine.arm()
    await engine.start()

    frame, detections = await engine.process_frame()
    await asyncio.sleep(10)
    await engine.stop()

asyncio.run(main())
```
