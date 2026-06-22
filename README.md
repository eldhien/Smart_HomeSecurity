# 🏠 Smart Home Security System: IoT & Computer Vision Integration

Proyek ini adalah sistem keamanan pintar rumah (**Smart Home Security**) yang mengintegrasikan teknologi **Computer Vision** berbasis Python dengan perangkat **Internet of Things (IoT)** berbasis ESP32. Sistem ini dirancang untuk melakukan pemantauan kondisi lingkungan fisik secara real-time dan deteksi wajah otomatis untuk mendeteksi ancaman keamanan atau tamu asing (Unknown).

---

## 🚀 Teknologi yang Digunakan

Proyek ini menggabungkan perangkat keras IoT dan perangkat lunak berbasis Artificial Intelligence (AI) dengan teknologi pendukung berikut:

- **Hardware & IoT:**
  - **ESP32** (Microcontroller Utama)
  - **WiFi Communication** (Komunikasi nirkabel lokal)
  - **DHT22 Sensor** (Pengukur Suhu & Kelembaban)
  - **PIR Motion Sensor** (Pendeteksi Gerakan)
  - **IR Obstacle Sensor** (Pendeteksi Halangan / Tamu di Depan Pintu)
  - **LDR Sensor** (Pendeteksi Intensitas Cahaya / Sensor Lampu)
  - **Arduino IDE** (Pengembangan Firmware ESP32)

- **Software & Computer Vision:**
  - **Python** (Bahasa Pemrograman Utama)
  - **OpenCV** (Pengolahan Frame Kamera & Rendering UI)
  - **YOLOv8** (Deteksi Objek Manusia Secara Real-Time)
  - **Deep SORT** (Pelacakan Objek / Object Tracking)
  - **Face Recognition** (Pengenalan Wajah Berdasarkan Dataset)
  - **Computer Vision** (Algoritma Pengolahan Citra)

- **Notification Integration:**
  - **Telegram Bot API** (Notifikasi Real-Time & Antarmuka Kontrol Jarak Jauh)

---

## 📁 Struktur Proyek

```text
├── config.py              # Konfigurasi token Telegram, parameter model, dan path dataset (diabaikan git)
├── config.py.example      # Contoh berkas konfigurasi parameter sistem
├── face_loader.py         # Skrip untuk meload dataset foto wajah yang dikenal
├── main.py                # Sistem deteksi lokal (tanpa integrasi Telegram)
├── main2.py               # Sistem deteksi cerdas lengkap dengan integrasi Telegram Bot
├── dataset/               # Folder dataset wajah yang dikenal
│   ├── Eldhien/           # Contoh dataset wajah 1 (diabaikan git)
│   └── johan/             # Contoh dataset wajah 2 (diabaikan git)
├── IOT/
│   └── sketch_may11a.ino  # Firmware Arduino IDE untuk ESP32 dan modul sensor
├── Models/
│   └── yolov8n.pt         # Bobot model YOLOv8 Nano untuk deteksi manusia
└── output/
    └── unknown/           # Direktori penyimpanan tangkapan layar wajah tidak dikenal (Unknown)
```

---

## ⚙️ Cara Kerja Sistem

Sistem ini terbagi menjadi dua sub-sistem utama yang bekerja secara sinergis melalui jaringan internet dan Telegram:

### 1. Computer Vision (Python)

Bagian ini bertanggung jawab dalam menangkap feed video kamera, mendeteksi manusia, melacak pergerakan mereka, serta mengenali wajah mereka.

- **`main.py` (Pendeteksi Tanpa Telegram):**
  - Berjalan secara lokal menggunakan webcam internal laptop atau kamera external.
  - Mendeteksi objek manusia menggunakan **YOLOv8**.
  - Melacak pergerakan menggunakan tracker **Deep SORT**.
  - Mengenali wajah menggunakan pustaka **Face Recognition** dengan membandingkannya terhadap dataset di folder `dataset/`.
  - Menyimpan tangkapan layar wajah tidak dikenal ke folder `output/unknown/` sebagai bukti keamanan.

- **`main2.py` (Pendeteksi Terintegrasi Telegram):**
  - Memiliki semua fungsionalitas `main.py`.
  - Terhubung secara aktif dengan **Telegram Bot API** menggunakan background thread listener.
  - Mengirimkan notifikasi pesan dan foto tangkapan layar secara otomatis ke Telegram jika mendeteksi wajah asing/tidak dikenal (**Unknown**).
  - Menerima instruksi perintah jarak jauh dari pengguna Telegram seperti `/takepicture` untuk mengambil foto kondisi rumah saat ini secara langsung.

### 2. Internet of Things / IoT (ESP32)

Berkas **`IOT/sketch_may11a.ino`** di-upload ke mikrokontroler ESP32 untuk memantau keadaan fisik rumah:

- **Suhu & Kelembaban:** Dipantau menggunakan sensor **DHT22**.
- **Keamanan Pintu:** Menggunakan **IR Obstacle Sensor** untuk mendeteksi kehadiran orang tepat di depan pintu masuk.
- **Keamanan Ruangan:** Menggunakan **PIR Motion Sensor** untuk memantau pergerakan mencurigakan di dalam ruangan saat rumah kosong. Jika ada gerakan, ESP32 akan langsung mengirimkan pesan peringatan darurat ke Telegram.
- **Kontrol Lampu Otomatis:** Menggunakan **LDR Sensor** untuk mendeteksi intensitas cahaya dalam menentukan status lampu.
- **Interaktivitas Telegram:** Pengguna dapat mengirimkan perintah `/status` ke Telegram Bot, dan ESP32 akan membalas dengan laporan parameter sensor yang lengkap secara real-time.

---

## 🔌 Skema Pin Sensor pada ESP32

Hubungkan komponen sensor ke pin ESP32 sesuai konfigurasi berikut pada berkas `.ino`:

| Komponen / Sensor      | Pin ESP32  | Tipe Signal            | Deskripsi                            |
| :--------------------- | :--------- | :--------------------- | :----------------------------------- |
| **DHT22**              | **Pin 12** | Digital I/O            | Sensor Suhu dan Kelembaban           |
| **IR Obstacle Sensor** | **Pin 14** | Digital Input          | Pendeteksi objek/tamu di dekat pintu |
| **PIR Motion Sensor**  | **Pin 27** | Digital Input          | Sensor pendeteksi gerakan            |
| **LDR Sensor**         | **Pin 16** | Digital Input / Analog | Sensor intensitas cahaya             |

---

## 🛠️ Instalasi & Persiapan

### A. Persiapan Sisi Python (Computer Vision)

1. **Clone repositori ini dan masuk ke direktori proyek:**

   ```bash
   cd "Smart Home Security"
   ```

2. **Buat dan aktifkan Virtual Environment (Direkomendasikan):**

   ```bash
   python -m venv venv
   # Di Windows (PowerShell)
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependensi library yang dibutuhkan:**

   ```bash
   pip install ultralytics opencv-python face-recognition requests deep-sort-realtime
   ```

   _(Catatan: Penginstalan `face_recognition` memerlukan kompilator C++ seperti CMake dan Visual Studio C++ build tools terinstall di PC Anda)._

4. **Konfigurasi Variabel Lingkungan:**
   - Salin file `config.py.example` menjadi `config.py`.
   - Isi token Telegram Bot Anda dan Chat ID akun Telegram Anda pada bagian:
     ```python
     TELEGRAM_BOT_TOKEN = "TOKEN_BOT_TELEGRAM_ANDA"
     TELEGRAM_CHAT_ID = "CHAT_ID_TELEGRAM_ANDA"
     ```

5. **Siapkan Dataset Wajah:**
   - Buat folder dengan nama orang yang ingin dikenali di dalam folder `dataset/` (misalnya `dataset/Eldhien/` atau `dataset/johan/`).
   - Masukkan foto wajah orang tersebut ke dalam folder masing-masing.

### B. Persiapan Sisi ESP32 (Arduino IDE)

1. Buka software **Arduino IDE**.
2. Pasang library berikut melalui **Library Manager** (`Ctrl+Shift+I`):
   - `DHT sensor library` oleh Adafruit
   - `UniversalTelegramBot` oleh Brian Gallacher
   - `ArduinoJson` oleh Benoit Blanchon (Versi 6.x direkomendasikan)
3. Buka berkas `IOT/sketch_may11a.ino`.
4. Sesuaikan konfigurasi jaringan WiFi dan Token Telegram Anda:
   ```cpp
   const char* ssid = "SSID_WIFI_ANDA";
   const char* password = "PASSWORD_WIFI_ANDA";
   #define BOTtoken "TOKEN_BOT_TELEGRAM_ANDA"
   #define CHAT_ID "CHAT_ID_TELEGRAM_ANDA"
   ```
5. Pilih board **ESP32 Dev Module** dan upload kode tersebut ke perangkat ESP32 Anda.

---

## 🚦 Cara Menjalankan Aplikasi

### Menjalankan Pendeteksi Tanpa Telegram (Lokal)

Jika Anda hanya ingin menjalankan visualisasi deteksi objek wajah dan pelacakan manusia secara lokal di layar PC tanpa notifikasi online:

```bash
python main.py
```

### Menjalankan Pendeteksi Lengkap dengan Telegram

Untuk mengaktifkan pendeteksi pintar yang dapat berinteraksi dengan Bot Telegram (mengirim peringatan unknown face dan menerima perintah `/takepicture`):

```bash
python main2.py
```

### Menjalankan Sistem Monitoring Sensor (ESP32)

Cukup hubungkan ESP32 Anda ke sumber daya (USB/Adapter). ESP32 akan otomatis menyambung ke WiFi dan siap memproses perintah `/status` atau mengirim peringatan gerakan (`PIR`).

---

## 🛡️ Keamanan & Privasi

Sesuai dengan berkas konfigurasi `.gitignore`, direktori sensitif berikut telah dikonfigurasi untuk tidak diunggah ke repositori publik:

- `config.py` (Berisi kredensial Token Bot Telegram dan Chat ID).
- `dataset/Eldhien/` & `dataset/johan/` (Berisi data pribadi foto wajah).
- `output/unknown/` (Tangkapan layar wajah asing yang terdeteksi).
- `venv/` (Folder virtual environment lokal).
