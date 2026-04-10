import json
from channels.generic.websocket import AsyncWebsocketConsumer


class InstallationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer. The p5.js frontend connects here.
    OpenCV sends gesture events via the channel layer.
    """

    GROUP_NAME = "installation"

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()
        print("Frontend connected")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)
        print("Frontend disconnected")

    # Called when the frontend sends a message (optional, for future use)
    async def receive(self, text_data):
        pass

    # Called by channel layer when OpenCV sends a gesture event
    async def gesture_event(self, event):
        await self.send(text_data=json.dumps({
            "type": "gesture",
            "event": event["gesture"],
            "data": event.get("data", {}),
        }))

    # Called by channel layer when OpenCV sends a scene change
    async def scene_event(self, event):
        await self.send(text_data=json.dumps({
            "type": "scene",
            "scene": event["scene"],
        }))
