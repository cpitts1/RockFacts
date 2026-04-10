from django.urls import re_path
from .consumers import InstallationConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/installation/$",
        InstallationConsumer.as_asgi()
    ),
]