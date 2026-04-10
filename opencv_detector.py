"""
opencv_detector.py

Run this script independently alongside Django.
It reads from the camera, detects motion/position,
and sends gesture events to the Django Channels layer.

Usage:
    python opencv_detector.py

Requirements:
    pip install opencv-python channels-redis
"""

import asyncio
import cv2
import numpy as np
from channels.layers import get_channel_layer


CHANNEL_GROUP = "installation"
CAMERA_INDEX = 0          # 0 = default webcam, change for external camera
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

# Zones: divide frame into thirds horizontally
ZONE_LEFT = 1 / 3
ZONE_RIGHT = 2 / 3


async def send_gesture(channel_layer, gesture: str, data: dict = {}):
    """Send a gesture event to all connected WebSocket clients."""
    await channel_layer.group_send(
        CHANNEL_GROUP,
        {
            "type": "gesture_event",   # maps to consumer method name
            "gesture": gesture,
            "data": data,
        }
    )


async def send_scene(channel_layer, scene: str):
    """Tell the frontend to switch landscape scene."""
    await channel_layer.group_send(
        CHANNEL_GROUP,
        {
            "type": "scene_event",
            "scene": scene,
        }
    )


async def run_detector():
    channel_layer = get_channel_layer()
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    # Background subtractor — learns what the empty wall looks like
    bg_subtractor = cv2.createBackgroundSubtractorMOG2(
        history=500,
        varThreshold=50,
        detectShadows=False,
    )

    last_zone = None
    scenes = ["forest", "ocean", "desert", "tundra", "jungle"]
    scene_index = 0

    print("OpenCV detector running. Press Q in the debug window to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Camera read failed — check CAMERA_INDEX")
            break

        frame = cv2.flip(frame, 1)  # mirror so movement feels natural
        h, w = frame.shape[:2]

        # --- Foreground mask ---
        fg_mask = bg_subtractor.apply(frame)
        fg_mask = cv2.morphologyEx(
            fg_mask, cv2.MORPH_OPEN,
            np.ones((5, 5), np.uint8)
        )

        # --- Find contours (people) ---
        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        large_contours = [c for c in contours if cv2.contourArea(c) > 5000]

        if large_contours:
            # Use the largest contour as the primary person
            person = max(large_contours, key=cv2.contourArea)
            x, y, cw, ch = cv2.boundingRect(person)
            centre_x = x + cw / 2

            # Determine horizontal zone
            rel_x = centre_x / w
            if rel_x < ZONE_LEFT:
                zone = "left"
            elif rel_x > ZONE_RIGHT:
                zone = "right"
            else:
                zone = "centre"

            # Fire gesture event only when zone changes
            if zone != last_zone:
                print(f"Zone changed: {zone}")
                await send_gesture(channel_layer, f"move_{zone}", {"x": rel_x})

                # Change scene when moving to left or right edge
                if zone == "left":
                    scene_index = (scene_index - 1) % len(scenes)
                    await send_scene(channel_layer, scenes[scene_index])
                elif zone == "right":
                    scene_index = (scene_index + 1) % len(scenes)
                    await send_scene(channel_layer, scenes[scene_index])

                last_zone = zone

            # Debug: draw bounding box and zone on frame
            cv2.rectangle(frame, (x, y), (x + cw, y + ch), (0, 255, 0), 2)
            cv2.putText(frame, zone, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # Zone dividers for debug view
        cv2.line(frame, (int(w * ZONE_LEFT), 0), (int(w * ZONE_LEFT), h), (255, 0, 0), 1)
        cv2.line(frame, (int(w * ZONE_RIGHT), 0), (int(w * ZONE_RIGHT), h), (255, 0, 0), 1)

        cv2.imshow("OpenCV debug — camera feed", frame)
        cv2.imshow("Foreground mask", fg_mask)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        await asyncio.sleep(0)  # yield to event loop

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    import django
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    asyncio.run(run_detector())
