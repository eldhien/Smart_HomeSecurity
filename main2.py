from ultralytics import YOLO
import cv2
import os
import threading
import time
from datetime import datetime

import face_recognition
import requests
from deep_sort_realtime.deepsort_tracker import DeepSort

from face_loader import load_known_faces
import config


model = YOLO(config.YOLO_MODEL)
tracker = DeepSort(
    max_age=config.DEEPSORT_MAX_AGE,
    n_init=config.DEEPSORT_N_INIT,
    max_cosine_distance=config.DEEPSORT_MAX_COSINE_DISTANCE,
)

known_encodings, known_names = load_known_faces()

saved_unknown_encodings = []
UNKNOWN_SAVE_TOLERANCE = 0.6
FACE_CHECK_INTERVAL = 2

stored_faces = []
track_names = {}
unknown_states = {}

last_frame = None
last_frame_lock = threading.Lock()
stop_event = threading.Event()


def telegram_enabled():
    token = str(getattr(config, "TELEGRAM_BOT_TOKEN", "")).strip()
    chat_id = str(getattr(config, "TELEGRAM_CHAT_ID", "")).strip()
    return (
        token
        and chat_id
        and token != "ISI_TOKEN_BOT_TELEGRAM"
        and chat_id != "ISI_CHAT_ID_TELEGRAM"
    )


def telegram_api_url(method):
    return f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{method}"


def send_telegram_message(text, chat_id=None):
    if not telegram_enabled():
        print("Telegram belum dikonfigurasi. Pesan:", text)
        return

    try:
        response = requests.post(
            telegram_api_url("sendMessage"),
            data={"chat_id": chat_id or config.TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
        if not response.ok:
            print("Warning: Telegram sendMessage gagal:", response.text)
    except requests.RequestException as e:
        print("Warning: Gagal mengirim pesan Telegram:", e)


def send_telegram_photo(frame, caption=None, chat_id=None):
    if frame is None:
        send_telegram_message("Kamera belum menangkap gambar.", chat_id=chat_id)
        return

    if not telegram_enabled():
        print("Telegram belum dikonfigurasi. Foto tidak dikirim.")
        return

    ok, buffer = cv2.imencode(".jpg", frame)
    if not ok:
        print("Warning: Gagal membuat gambar dari frame kamera.")
        return

    files = {"photo": ("camera.jpg", buffer.tobytes(), "image/jpeg")}
    data = {"chat_id": chat_id or config.TELEGRAM_CHAT_ID}
    if caption:
        data["caption"] = caption

    try:
        response = requests.post(
            telegram_api_url("sendPhoto"),
            data=data,
            files=files,
            timeout=20,
        )
        if not response.ok:
            print("Warning: Telegram sendPhoto gagal:", response.text)
    except requests.RequestException as e:
        print("Warning: Gagal mengirim foto Telegram:", e)


def get_current_frame():
    with last_frame_lock:
        if last_frame is None:
            return None
        return last_frame.copy()


def normalize_command(text):
    command = text.strip().split()[0].lower()
    return command.split("@")[0]


def telegram_command_listener():
    if not telegram_enabled():
        print("Telegram belum aktif. Isi TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID di config.py")
        return

    print("Telegram listener aktif. Command: /takepicture atau /takeficture")
    offset = None

    while not stop_event.is_set():
        try:
            params = {"timeout": 10}
            if offset is not None:
                params["offset"] = offset

            response = requests.get(
                telegram_api_url("getUpdates"),
                params=params,
                timeout=15,
            )
            if not response.ok:
                print("Warning: Telegram getUpdates gagal:", response.text)
                time.sleep(5)
                continue

            updates = response.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message", {})
                text = message.get("text", "")
                chat_id = str(message.get("chat", {}).get("id", ""))

                if not text:
                    continue

                command = normalize_command(text)

                if command == "/chatid":
                    send_telegram_message(f"Chat ID kamu: {chat_id}", chat_id=chat_id)
                    continue

                if chat_id != str(config.TELEGRAM_CHAT_ID):
                    print(f"Command dari chat ID berbeda diabaikan: {chat_id}")
                    continue

                if command in ("/takepicture", "/takeficture"):
                    frame = get_current_frame()
                    send_telegram_photo(frame, "Keadaan kamera saat ini", chat_id=chat_id)

        except requests.RequestException as e:
            print("Warning: Telegram listener error:", e)
            time.sleep(5)


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


def update_unknown_alerts(active_track_ids, current_time, frame):
    for track_id in list(unknown_states.keys()):
        if track_id not in active_track_ids or track_names.get(track_id) != "Unknown":
            unknown_states.pop(track_id, None)

    for track_id in active_track_ids:
        if track_names.get(track_id, "Unknown") != "Unknown":
            continue

        state = unknown_states.setdefault(
            track_id,
            {
                "first_seen": current_time,
                "text_sent": False,
                "photo_sent": False,
            },
        )
        duration = current_time - state["first_seen"]

        if duration >= config.TELEGRAM_UNKNOWN_TEXT_DELAY and not state["text_sent"]:
            send_telegram_message("Ada orang tidak dikenal di depan rumah")
            state["text_sent"] = True

        if duration >= config.TELEGRAM_UNKNOWN_PHOTO_DELAY and not state["photo_sent"]:
            send_telegram_photo(frame, "Orang tidak dikenal terdeteksi lebih dari 30 detik")
            state["photo_sent"] = True


def save_unknown_face_if_needed(current_time):
    unknown_face = next(
        (face for face in stored_faces if face["name"] == "Unknown"),
        None,
    )
    if unknown_face is None:
        return

    state = unknown_states.get(unknown_face["track_id"])
    if state is None or state.get("saved_face"):
        return

    if current_time - state["first_seen"] < config.DELAY_30:
        return

    face_encoding = unknown_face["encoding"]
    already_saved = False

    if len(saved_unknown_encodings) > 0:
        matches_unknown = face_recognition.compare_faces(
            saved_unknown_encodings,
            face_encoding,
            tolerance=UNKNOWN_SAVE_TOLERANCE,
        )
        already_saved = True in matches_unknown

    if already_saved:
        state["saved_face"] = True
        return

    frame = get_current_frame()
    if frame is None:
        return

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
    state["saved_face"] = True


telegram_thread = threading.Thread(target=telegram_command_listener, daemon=True)
telegram_thread.start()

# URL_HP = "http://192.168.10.249:8080/video"
# cap = cv2.VideoCapture(URL_HP)
cap = cv2.VideoCapture(0)

frame_counter = 0

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Kamera tidak terbaca")
            break

        frame = cv2.resize(frame, (640, 480))
        current_time = time.time()

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
            except Exception as e:
                print("Warning: Error face encoding, skip frame:", e)
                stored_faces = []
        elif not detected_person:
            stored_faces = []

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

        with last_frame_lock:
            last_frame = frame.copy()

        update_unknown_alerts(active_track_ids, current_time, frame)
        save_unknown_face_if_needed(current_time)

        cv2.imshow("Smart Security Telegram", frame)

        frame_counter += 1

        if cv2.waitKey(1) == 27:
            break
finally:
    stop_event.set()
    cap.release()
    cv2.destroyAllWindows()
