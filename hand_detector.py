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
PINCH_THRESHOLD = 0.06    # normalized distance for pinch detection

# Landmark indices
WRIST = 0
THUMB_TIP = 4
INDEX_TIP = 8


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


def is_pinching(landmarks) -> bool:
    """Return True when thumb tip and index tip are close together."""
    thumb = landmarks[THUMB_TIP]
    index = landmarks[INDEX_TIP]
    dist = np.hypot(thumb.x - index.x, thumb.y - index.y)
    return dist < PINCH_THRESHOLD

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

            # frame = cv2.flip(frame, 1)  # mirror for natural interaction
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

            result = detector.detect(mp_image)

            detected_gestures = []
            for i, hand_landmarks in enumerate(result.hand_landmarks):
                wrist = hand_landmarks[WRIST]
                histories[i].append((wrist.x, wrist.y))

                motion = detect_motion(histories[i])
                pinch = is_pinching(hand_landmarks)

                label = motion or ('Pinch' if pinch else '')
                if label:
                    detected_gestures.append(label)

            # Clear histories for hands no longer detected
            for i in range(len(result.hand_landmarks), NUM_HANDS):
                histories[i].clear()

            # Annotate handedness
            for i, handedness in enumerate(result.handedness):
                side = handedness[0].display_name
                h, w = frame.shape[:2]
                wrist = result.hand_landmarks[i][WRIST]
                x, y = int(wrist.x * w), int(wrist.y * h) - 20
                draw_label(frame, side, (x, y), color=(255, 200, 0))

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
