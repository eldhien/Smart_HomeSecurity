import face_recognition
import os
from config import DATASET_PATH

VALID_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp')

def load_known_faces():
    known_encodings = []
    known_names = []

    for person_name in os.listdir(DATASET_PATH):
        person_folder = os.path.join(DATASET_PATH, person_name)

        if not os.path.isdir(person_folder):
            continue

        for img_name in os.listdir(person_folder):

            # Skip file non-gambar
            if not img_name.lower().endswith(VALID_EXTENSIONS):
                print(f"Skip non-image: {img_name}")
                continue

            img_path = os.path.join(person_folder, img_name)

            try:
                image = face_recognition.load_image_file(img_path)
                encodings = face_recognition.face_encodings(image)

                if len(encodings) > 0:
                    known_encodings.append(encodings[0])
                    known_names.append(person_name)
                else:
                    print(f"Tidak ada wajah pada: {img_name}")

            except Exception as e:
                print(f"Gagal membaca {img_name}: {e}")

    print(f"Loaded {len(known_names)} wajah")
    return known_encodings, known_names