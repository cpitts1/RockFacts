# RockFacts
An interactive art installation that projects living landscapes onto a wall and responds to people moving through the space. OpenCV tracks visitors via camera, Django relays gesture events over WebSockets, and p5.js renders the landscapes in a browser driving the projector.

---

## Architecture

```
Camera → OpenCV (Python) → Django Channels → WebSocket → p5.js (browser) → Projector
                                    ↕
                                  Redis
                                    ↕
                            Django REST API
                            (landscapes & facts)
```

**How it fits together:**
- `opencv_detector.py` reads the camera, detects where people are, and fires gesture events via the Redis channel layer
- `consumers.py` (Django Channels) relays those events to any connected WebSocket clients
- `index.html` (p5.js) listens on the WebSocket and changes the rendered landscape in response
- The Django admin panel lets you edit landscape content and facts without touching code

---

## Tech stack

| Tool | Purpose | Cost |
|---|---|---|
| Python | Core language | Free |
| OpenCV | Camera + gesture detection | Free |
| Django | Web framework + REST API + admin | Free |
| Django Channels | WebSocket support | Free |
| channels-redis | Channel layer backend | Free |
| Redis | Message broker between processes | Free |
| Daphne / uvicorn | ASGI server (replaces runserver) | Free |
| p5.js | Landscape rendering in browser | Free |
| Docker | Run Redis without native install | Free |

---

## Project files

```
your-project/
├── README.md                  ← this file
├── manage.py
├── requirements.txt
├── venv/                      ← virtual environment (not in git)
├── config/
│   ├── settings.py
│   ├── asgi.py
│   └── urls.py
└── installation/
    ├── consumers.py           ← WebSocket consumer
    ├── routing.py             ← WebSocket URL routing
    ├── opencv_detector.py     ← OpenCV gesture detection
    ├── models.py              ← Landscape + Fact models
    ├── views.py               ← REST API views
    └── index.html             ← p5.js frontend
```

---

## One-time setup

### 1. Create and activate virtual environment

```bash
# In your project root (same folder as manage.py)
python -m venv venv

# Activate (Mac / Linux)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install django channels channels-redis daphne opencv-python numpy
pip freeze > requirements.txt
```

### 3. Start Redis

```bash
docker run -d -p 6379:6379 --name redis-installation redis:7.2
```

Verify: `redis-cli ping` → should return `PONG`

### 4. Configure settings.py

Add to `INSTALLED_APPS`:
```python
"channels",
"installation",
```

Add at the bottom:
```python
ASGI_APPLICATION = "config.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [("127.0.0.1", 6379)]},
    }
}
```

### 5. Replace config/asgi.py

```python
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from installation.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(websocket_urlpatterns),
})
```

### 6. Run migrations and create superuser

```bash
python manage.py migrate
python manage.py createsuperuser
```

---

## Running the installation

Three terminal windows, all with the virtual environment activated:

**Terminal 1 — Django (ASGI server)**
```bash
source venv/bin/activate
daphne -p 8000 config.asgi:application
```

**Terminal 2 — OpenCV detector**
```bash
source venv/bin/activate
python installation/opencv_detector.py
```

**Terminal 3 — open the frontend**
```bash
open installation/index.html
# or serve via Django and visit http://localhost:8000
```

Press **Q** in the OpenCV debug window to stop the detector.

---

## Smoke test (verify the full pipeline)

With Django running and `index.html` open in a browser (DevTools console open):

```bash
python manage.py shell
```

```python
import asyncio
from channels.layers import get_channel_layer

layer = get_channel_layer()
asyncio.run(layer.group_send(
    "installation",
    {"type": "gesture_event", "gesture": "move_left", "data": {}},
))
```

You should see the message appear in the browser console and the landscape change. If it does — the full pipeline is confirmed working.

---

## Projector calibration

With `index.html` open and the projector running, press **C** to toggle the calibration grid overlay. Use this to align the projection to your wall before an installation. Adjust `ZONE_LEFT` and `ZONE_RIGHT` in `opencv_detector.py` to match the projected image boundaries.

---

## Development roadmap

### Phase 1 — Environment & skeleton (weeks 1–3)

- [ ] Create virtual environment and install all dependencies
- [ ] Get Django + Channels + Redis running (Daphne serving on localhost)
- [ ] Wire `consumers.py` into routing, confirm WebSocket connects in browser
- [ ] Run smoke test — gesture event from Django shell appears in browser console
- [ ] Run `opencv_detector.py`, confirm camera opens and debug windows appear
- [ ] Walk in front of camera, cross a zone, watch landscape change in browser

### Phase 2 — OpenCV gesture logic (weeks 4–7)

- [ ] Calibrate `ZONE_LEFT` / `ZONE_RIGHT` to match your projected wall width
- [ ] Tune `BackgroundSubtractorMOG2` parameters for your room lighting
- [ ] Add gesture cooldown to prevent rapid repeated events
- [ ] Add vertical gesture detection (raised arms, crouching)
- [ ] Handle multiple people (multiple large contours)
- [ ] Create `GestureZone` Django model — remap gestures from admin panel

### Phase 3 — p5.js landscapes & facts (weeks 8–12)

- [ ] Build 5 distinct landscape scenes with unique noise parameters and palettes
- [ ] Create `Landscape` and `Fact` Django models
- [ ] Serve facts via Django REST API
- [ ] Fetch and display facts as overlays in p5.js on scene change
- [ ] Implement smooth scene crossfades using `createGraphics` buffers
- [ ] Add ambient audio per scene (Web Audio API or Tone.js)
- [ ] Run first audience test with 2–3 people — observe silently, take notes

### Phase 4 — Hardening & launch (weeks 13–16)

- [ ] Wrap OpenCV detector in supervisord for auto-restart on crash
- [ ] Verify WebSocket auto-reconnect logic works in `index.html`
- [ ] Add Django file logging for Daphne and the detector
- [ ] Build calibration grid overlay in p5.js (press C to toggle)
- [ ] Create `InteractionLog` Django model — log gesture events with timestamps
- [ ] Write setup procedure (hardware placement, camera angle, projector distance)
- [ ] Plan and record installation video from audience perspective
- [ ] Post-installation: query interaction logs, review what worked

---

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `ConnectionRefusedError` in shell | Redis not running | `docker ps` — start container if stopped |
| WebSocket not connecting in browser | Daphne not running or wrong port | Check terminal 1 for errors |
| Camera not opening | Wrong `CAMERA_INDEX` | Try `0`, `1`, `2` in `opencv_detector.py` |
| No gesture events firing | Contour area threshold too high | Lower `5000` in `large_contours` filter |
| Landscape not changing | Zone boundaries wrong | Print `rel_x` values and adjust `ZONE_LEFT`/`ZONE_RIGHT` |
| Dark / washed out projection | Projector colour profile | Boost saturation in p5 colour values |

---

## .gitignore

```
venv/
__pycache__/
*.pyc
db.sqlite3
.env
```

---

## Useful commands

```bash
# Check Redis is running
redis-cli ping

# Stop Redis container
docker stop redis-installation

# Start Redis container again
docker start redis-installation

# See all installed packages
pip list

# Recreate environment on a new machine
pip install -r requirements.txt

# Open Django admin
# Visit http://localhost:8000/admin after running migrations
```