"""
opencv_detector.py

Run this script independently alongside Django.
It reads from the camera, detects hand gestures,
and sends scene events to the Django Channels layer.

A closed fist held in one of the four screen quadrants triggers the
scene assigned to that quadrant.

Usage:
    python opencv_detector.py

Requirements:
    pip install opencv-python mediapipe channels-redis
"""

import asyncio
import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from channels.layers import get_channel_layer


CHANNEL_GROUP = "installation"
CAMERA_INDEX = 0 # This is the default camera
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

MODEL_PATH = 'hand_landmarker.task'
NUM_HANDS = 1

# Landmark indices
WRIST = 0
INDEX_TIP = 8
INDEX_PIP = 6
MIDDLE_TIP = 12
MIDDLE_PIP = 10
RING_TIP = 16
RING_PIP = 14
PINKY_TIP = 20
PINKY_PIP = 18

# Quadrant → scene mapping (top-left, top-right, bottom-left, bottom-right)
QUADRANT_SCENES = {
    "top_left":     "forest",
    "top_right":    "ocean",
    "bottom_left":  "desert",
    "bottom_right": "tundra",
}


def build_detector() -> vision.HandLandmarker:
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
        num_hands=NUM_HANDS,
    )
    return vision.HandLandmarker.create_from_options(options)


def is_closed_fist(landmarks) -> bool:
    """Return True when all four fingers are curled (closed fist)."""
    def curled(tip, pip):
        return landmarks[tip].y > landmarks[pip].y

    return (
        curled(INDEX_TIP, INDEX_PIP)
        and curled(MIDDLE_TIP, MIDDLE_PIP)
        and curled(RING_TIP, RING_PIP)
        and curled(PINKY_TIP, PINKY_PIP)
    )


def get_quadrant(x: float, y: float) -> str:
    """Return quadrant name for normalized (x, y) wrist coordinates."""
    v = "top" if y < 0.5 else "bottom"
    h = "left" if x < 0.5 else "right"
    return f"{v}_{h}"


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
    detector = build_detector()

    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

    last_fist_quadrant = None

    print("OpenCV detector running. Press Q in the debug window to quit.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Camera read failed — check CAMERA_INDEX")
                break

            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]

            # Draw quadrant dividers
            cv2.line(frame, (w // 2, 0), (w // 2, h), (255, 0, 0), 1)
            cv2.line(frame, (0, h // 2), (w, h // 2), (255, 0, 0), 1)

            # Label each quadrant with its scene name
            quadrant_labels = [
                ("forest",  (10,          30)),
                ("ocean",   (w // 2 + 10, 30)),
                ("desert",  (10,          h // 2 + 30)),
                ("tundra",  (w // 2 + 10, h // 2 + 30)),
            ]
            for text, pos in quadrant_labels:
                cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (200, 200, 200), 1, cv2.LINE_AA)

            # Run hand detection
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = detector.detect(mp_image)

            fist_quadrant = None

            for hand_landmarks in result.hand_landmarks:
                wrist = hand_landmarks[WRIST]
                quadrant = get_quadrant(wrist.x, wrist.y)

                px, py = int(wrist.x * w), int(wrist.y * h)
                cv2.circle(frame, (px, py), 8, (0, 255, 0), -1)

                if is_closed_fist(hand_landmarks):
                    fist_quadrant = quadrant
                    cv2.putText(frame, f"FIST: {quadrant}", (px + 12, py),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                else:
                    cv2.putText(frame, quadrant, (px + 12, py),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)

            # Trigger scene change when a fist appears in a new quadrant
            if fist_quadrant and fist_quadrant != last_fist_quadrant:
                scene = QUADRANT_SCENES[fist_quadrant]
                print(f"Fist in {fist_quadrant} → scene: {scene}")
                await send_scene(channel_layer, scene)
                last_fist_quadrant = fist_quadrant
            elif not fist_quadrant:
                last_fist_quadrant = None  # reset so the same quadrant can fire again

            cv2.imshow("OpenCV debug — camera feed", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            await asyncio.sleep(0)

    finally:
        cap.release()
        cv2.destroyAllWindows()
        detector.close()


if __name__ == "__main__":
    import django
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    asyncio.run(run_detector())
