from ultralytics import YOLO
import cv2
import time
import os
from datetime import datetime
import face_recognition
from deep_sort_realtime.deepsort_tracker import DeepSort

from face_loader import load_known_faces
import config

# Load model YOLO
model = YOLO(config.YOLO_MODEL)
tracker = DeepSort(
    max_age=config.DEEPSORT_MAX_AGE,
    n_init=config.DEEPSORT_N_INIT,
    max_cosine_distance=config.DEEPSORT_MAX_COSINE_DISTANCE,
)

known_encodings, known_names = load_known_faces()

# Unknown faces sudah disimpan
saved_unknown_encodings = []
UNKNOWN_SAVE_TOLERANCE = 0.6

stored_faces = []
track_names = {}
unknown_start_time = None
unknown_saved = False

# URL_HP = "http://192.168.10.249:8080/video"
# cap = cv2.VideoCapture(URL_HP)

cap = cv2.VideoCapture(0)

frame_counter = 0
FACE_CHECK_INTERVAL = 2


def find_track_for_face(face, tracks):
    top = face["top"]
    right = face["right"]
    bottom = face["bottom"]
    left = face["left"]
    face_center_x = (left + right) / 2
    face_center_y = (top + bottom) / 2

    best_track_id = None
    best_area = None

    for track in tracks:
        if not track.is_confirmed() or track.time_since_update > 1:
            continue

        x1, y1, x2, y2 = map(int, track.to_ltrb())
        if x1 <= face_center_x <= x2 and y1 <= face_center_y <= y2:
            area = max(0, x2 - x1) * max(0, y2 - y1)
            if best_area is None or area < best_area:
                best_track_id = track.track_id
                best_area = area

    return best_track_id


def recognize_face(face_encoding):
    if not known_encodings:
        return "Unknown"

    distances = face_recognition.face_distance(known_encodings, face_encoding)
    best_match_idx = distances.argmin()

    if distances[best_match_idx] <= config.TOLERANCE:
        return known_names[best_match_idx]

    return "Unknown"


while True:
    ret, frame = cap.read()
    if not ret:
        print("Kamera tidak terbaca")
        break

    frame = cv2.resize(frame, (640, 480))
    current_time = time.time()

    # YOLO DETECTION (PERSON)
    results = model(frame, verbose=False)
    detections = []

    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            if model.names[cls] == "person":
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                confidence = float(box.conf[0])
                width = x2 - x1
                height = y2 - y1
                detections.append(([x1, y1, width, height], confidence, "person"))

    tracks = tracker.update_tracks(detections, frame=frame)
    active_track_ids = {
        track.track_id
        for track in tracks
        if track.is_confirmed() and track.time_since_update <= 1
    }
    tracks_to_check = {
        track_id
        for track_id in active_track_ids
        if track_names.get(track_id, "Unknown") == "Unknown"
    }

    detected_person = len(active_track_ids) > 0

    # FACE RECOGNITION (only when person visible)
    face_locations = []
    face_encodings = []
    unknown_detected = False

    if (
        detected_person
        and tracks_to_check
        and (frame_counter % FACE_CHECK_INTERVAL == 0 or not stored_faces)
    ):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        face_locations = [
            (int(top), int(right), int(bottom), int(left))
            for (top, right, bottom, left) in face_locations
        ]

        try:
            if len(face_locations) > 0:
                face_track_pairs = []
                for top, right, bottom, left in face_locations:
                    face = {
                        "top": top,
                        "right": right,
                        "bottom": bottom,
                        "left": left,
                    }
                    track_id = find_track_for_face(face, tracks)
                    if track_id in tracks_to_check:
                        face_track_pairs.append(((top, right, bottom, left), track_id))

                face_locations = [location for location, _ in face_track_pairs]
                face_encodings = face_recognition.face_encodings(
                    rgb_frame, face_locations
                )
                stored_faces = []

                for ((top, right, bottom, left), track_id), face_encoding in zip(
                    face_track_pairs, face_encodings
                ):
                    name = recognize_face(face_encoding)

                    if name == "Unknown":
                        unknown_detected = True

                    stored_faces.append(
                        {
                            "top": top,
                            "right": right,
                            "bottom": bottom,
                            "left": left,
                            "name": name,
                            "encoding": face_encoding,
                            "track_id": track_id,
                        }
                    )
                    track_names[track_id] = name

                if unknown_detected:
                    if unknown_start_time is None:
                        unknown_start_time = current_time
                else:
                    unknown_start_time = None
                    unknown_saved = False
        except Exception as e:
            print("Warning: Error face encoding, skip frame:", e)
            face_locations = []
            face_encodings = []
            stored_faces = []
            unknown_start_time = None
            unknown_saved = False

    elif detected_person and stored_faces:
        unknown_detected = any(face["name"] == "Unknown" for face in stored_faces)
    else:
        stored_faces = []
        unknown_start_time = None
        unknown_saved = False

    for track in tracks:
        if not track.is_confirmed() or track.time_since_update > 1:
            continue

        track_id = track.track_id
        name = track_names.get(track_id, "Unknown")
        x1, y1, x2, y2 = map(int, track.to_ltrb())
        color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
        label = f"ID: {track_id} | {name}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            frame,
            label,
            (x1, max(20, y1 - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
        )

    if unknown_detected and not unknown_saved and unknown_start_time is not None:
        if current_time - unknown_start_time >= config.DELAY_30:
            unknown_face = next(
                (face for face in stored_faces if face["name"] == "Unknown"),
                None,
            )
            if unknown_face is not None:
                face_encoding = unknown_face["encoding"]
                already_saved = False

                if len(saved_unknown_encodings) > 0:
                    matches_unknown = face_recognition.compare_faces(
                        saved_unknown_encodings,
                        face_encoding,
                        tolerance=UNKNOWN_SAVE_TOLERANCE,
                    )
                    already_saved = True in matches_unknown

                if not already_saved:
                    os.makedirs(config.UNKNOWN_PATH, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"{config.UNKNOWN_PATH}/unknown_{timestamp}.jpg"
                    top = unknown_face["top"]
                    right = unknown_face["right"]
                    bottom = unknown_face["bottom"]
                    left = unknown_face["left"]
                    face_image = frame[top:bottom, left:right]
                    if face_image.size == 0:
                        face_image = frame
                    cv2.imwrite(filename, face_image)
                    saved_unknown_encodings.append(face_encoding)

                unknown_saved = True

    cv2.imshow("Smart Security", frame)

    frame_counter += 1

    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()
