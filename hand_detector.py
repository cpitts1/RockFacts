import cv2
import mediapipe as mp
import numpy as np
from collections import deque
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# --- Constants ---
MODEL_PATH = 'hand_landmarker.task'
NUM_HANDS = 2
MOTION_HISTORY = 15       # frames to track for motion detection
MOTION_THRESHOLD = 0.05   # normalized coordinate distance to register a swipe
# Landmark indices
WRIST = 0
THUMB_TIP = 4
INDEX_TIP = 8
INDEX_PIP = 6
MIDDLE_TIP = 12
MIDDLE_PIP = 10
RING_TIP = 16
RING_PIP = 14
PINKY_TIP = 20
PINKY_PIP = 18


def build_detector() -> vision.HandLandmarker:
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
        num_hands=NUM_HANDS,
    )
    return vision.HandLandmarker.create_from_options(options)


def detect_motion(history: deque) -> str:
    """Classify wrist motion from a deque of (x, y) positions."""
    if len(history) < 2:
        return ''
    dx = history[-1][0] - history[0][0]
    dy = history[-1][1] - history[0][1]
    if abs(dx) < MOTION_THRESHOLD and abs(dy) < MOTION_THRESHOLD:
        return ''
    if abs(dx) > abs(dy):
        return 'Swipe Right' if dx > 0 else 'Swipe Left'
    return 'Swipe Down' if dy > 0 else 'Swipe Up'


def is_open(landmarks) -> bool:
    """Return True when all four fingers are extended."""
    def extended(tip, pip):
        return landmarks[tip].y < landmarks[pip].y

    return (
        extended(INDEX_TIP, INDEX_PIP)
        and extended(MIDDLE_TIP, MIDDLE_PIP)
        and extended(RING_TIP, RING_PIP)
        and extended(PINKY_TIP, PINKY_PIP)
    )


def draw_label(frame: np.ndarray, text: str, pos: tuple, color=(0, 255, 0)) -> None:
    cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2, cv2.LINE_AA)


def main() -> None:
    detector = build_detector()
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam.")

    # One motion history deque per hand slot (up to NUM_HANDS)
    histories = [deque(maxlen=MOTION_HISTORY) for _ in range(NUM_HANDS)]

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)  # mirror for natural interaction
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            result = detector.detect(mp_image)

            detected_gestures = []
            for i, hand_landmarks in enumerate(result.hand_landmarks):
                wrist = hand_landmarks[WRIST]
                histories[i].append((wrist.x, wrist.y))

                motion = detect_motion(histories[i])
                open_hand = is_open(hand_landmarks)

                label = motion or ('Open' if open_hand else 'Closed')
                detected_gestures.append(label)

            # Clear histories for hands no longer detected
            for i in range(len(result.hand_landmarks), NUM_HANDS):
                histories[i].clear()

            if detected_gestures:
                draw_label(frame, ' | '.join(detected_gestures), (10, 50))

            draw_label(frame, f"Hands: {len(result.hand_landmarks)}", (10, frame.shape[0] - 15),
                       color=(200, 200, 200))

            cv2.imshow('Hand Motion Detector', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        detector.close()


if __name__ == '__main__':
    main()
