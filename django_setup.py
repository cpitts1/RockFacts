# routing.py — add to your Django project root
# -----------------------------------------------
from django.urls import re_path
from installation.consumers import InstallationConsumer

websocket_urlpatterns = [
    re_path(r"ws/installation/$", InstallationConsumer.as_asgi()),
]


# asgi.py — replace your project's asgi.py with this
# -----------------------------------------------
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.layers import get_channel_layer
from routing import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(websocket_urlpatterns),
})


# settings.py additions — add these to your existing settings
# -----------------------------------------------
INSTALLED_APPS = [
    # ... your existing apps ...
    "channels",
    "installation",
]

ASGI_APPLICATION = "config.asgi.application"

# Channel layer — uses Redis (run: docker run -p 6379:6379 redis)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [("127.0.0.1", 6379)]},
    }
}


# requirements.txt
# -----------------------------------------------
# django>=4.2
# channels>=4.0
# channels-redis>=4.0
# opencv-python>=4.8
# numpy>=1.24
# redis>=5.0


# How to run — three terminal windows
# -----------------------------------------------
# Terminal 1: Django (Daphne ASGI server)
#   pip install daphne
#   daphne -p 8000 config.asgi:application
#
# Terminal 2: OpenCV detector
#   python installation/opencv_detector.py
#
# Terminal 3: open the frontend
#   open installation/index.html   (or serve via Django static files)
