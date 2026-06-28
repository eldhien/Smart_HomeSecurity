#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <UniversalTelegramBot.h>
#include <ArduinoJson.h>
#include "DHT.h"

// =======================
// WIFI & TELEGRAM
// =======================
const char* ssid = "KOOSS";
const char* password = "kospojokbolo";

#define BOTtoken "8831957751:AAFRODWnWK69EVJtBMGaGFJAe_Cbj4s8mHw"
#define CHAT_ID "6319542865"

// =======================
// PIN SENSOR
// =======================
#define DHTPIN 21
#define DHTTYPE DHT22

#define LDR_PIN 16
#define PIR_PIN 35
#define IR_PIN 25

// =======================
// OBJECT
// =======================
DHT dht(DHTPIN, DHTTYPE);
WiFiClientSecure client;
UniversalTelegramBot bot(BOTtoken, client);

// =======================
// TIMER TELEGRAM
// =======================
unsigned long lastTimeBotRun = 0;
const unsigned long botInterval = 1000;

// =======================
// CACHE DHT 30 DETIK
// =======================
float cachedTemp = NAN;
float cachedHum = NAN;
unsigned long lastValidDhtTime = 0;
const unsigned long dhtCacheDuration = 30000;

// =======================
// PIR NOTIFICATION
// =======================
unsigned long lastPirAlert = 0;
const unsigned long pirCooldown = 15000;
bool lastPirState = LOW;

// =======================
// WIFI CONNECT
// =======================
void connectWiFi() {
  Serial.print("Connecting to WiFi");

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi Connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

// =======================
// BACA DHT + SIMPAN CACHE
// =======================
void readDHTWithDelay() {
  delay(2500);

  float t = dht.readTemperature();
  float h = dht.readHumidity();

  if (!isnan(t) && !isnan(h) && t > -20 && t < 80 && h >= 0 && h <= 100) {
    cachedTemp = t;
    cachedHum = h;
    lastValidDhtTime = millis();

    Serial.println("DHT22: Data valid disimpan");
  } else {
    Serial.println("DHT22: Gagal baca, memakai cache jika tersedia");
  }
}

// =======================
// STATUS REPORT
// =======================
String getStatusReport() {
  Serial.println("Membaca semua sensor untuk /status...");

  readDHTWithDelay();

  int ldrRaw = digitalRead(LDR_PIN);
  int irState = digitalRead(IR_PIN);
  int pirState = digitalRead(PIR_PIN);

  bool dhtCacheValid = !isnan(cachedTemp) &&
                       !isnan(cachedHum) &&
                       (millis() - lastValidDhtTime <= dhtCacheDuration);

  String kondisiLampu;
  String kondisiCahaya;
  String keberadaanOrang;
  String kondisiGerakan;

  Serial.print("RAW LDR = ");
  Serial.println(ldrRaw);

  if (ldrRaw == LOW) {
    Serial.println("Ada Cahaya");
    kondisiCahaya = "true";
    kondisiLampu = "HIDUP";
  } else {
    Serial.println("Tidak Ada Cahaya");
    kondisiCahaya = "false";
    kondisiLampu = "MATI";
  }

  keberadaanOrang = (irState == LOW) ? "ADA ORANG DI PINTU" : "AREA KOSONG";
  kondisiGerakan = (pirState == HIGH) ? "TERDETEKSI GERAKAN" : "TIDAK ADA GERAKAN";

  String report = "📊 STATUS RUANGAN SAAT INI\n\n";
  report += "💡 Kondisi Lampu: " + kondisiLampu + "\n";
  report += "🔆 Cahaya: " + kondisiCahaya + "\n";
  report += "🚶 Keberadaan Orang: " + keberadaanOrang + "\n";
  report += "🏃 Gerakan PIR: " + kondisiGerakan + "\n";

  if (dhtCacheValid) {
    report += "🌡️ Suhu Ruangan: " + String(cachedTemp, 1) + " °C\n";
    report += "💧 Kelembaban: " + String(cachedHum, 1) + " %\n";
  } else {
    report += "🌡️ Suhu Ruangan: Sensor gagal terbaca\n";
    report += "💧 Kelembaban: Sensor gagal terbaca\n";
  }

  return report;
}

// =======================
// HANDLE TELEGRAM MESSAGE
// =======================
void handleNewMessages(int numNewMessages) {
  for (int i = 0; i < numNewMessages; i++) {
    String chat_id = bot.messages[i].chat_id;
    String text = bot.messages[i].text;

    Serial.print("Pesan dari chat_id: ");
    Serial.println(chat_id);
    Serial.print("Isi pesan: ");
    Serial.println(text);

    if (text == "/start") {
      String welcome = "Bot IoT ESP32 aktif.\n\n";
      welcome += "Gunakan perintah:\n";
      welcome += "/status - Cek status ruangan";
      bot.sendMessage(chat_id, welcome, "");
    }

    else if (text == "/status") {
      bot.sendMessage(chat_id, "⏳ Membaca sensor, mohon tunggu...", "");

      String report = getStatusReport();
      bot.sendMessage(chat_id, report, "");
    }

    else {
      bot.sendMessage(chat_id, "Perintah tidak dikenal. Gunakan /status", "");
    }
  }
}

// =======================
// PIR AUTO NOTIFICATION
// =======================
void checkPIR() {
  int pirState = digitalRead(PIR_PIN);

  if (pirState == HIGH && lastPirState == LOW) {
    if (millis() - lastPirAlert > pirCooldown) {
      bot.sendMessage(CHAT_ID, "⚠️ PERINGATAN: Terdeteksi gerakan mencurigakan di dalam ruangan!", "");
      lastPirAlert = millis();
    }
  }

  lastPirState = pirState;
}

// =======================
// SETUP
// =======================
void setup() {
  Serial.begin(115200);
  delay(2000);

  pinMode(LDR_PIN, INPUT);
  pinMode(PIR_PIN, INPUT);
  pinMode(IR_PIN, INPUT);

  dht.begin();

  connectWiFi();

  client.setInsecure();

  bot.sendMessage(CHAT_ID, "✅ ESP32 IoT Bot berhasil online.", "");

  Serial.println("System Ready!");
}

// =======================
// LOOP
// =======================
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  if (millis() - lastTimeBotRun > botInterval) {
    int numNewMessages = bot.getUpdates(bot.last_message_received + 1);

    while (numNewMessages) {
      handleNewMessages(numNewMessages);
      numNewMessages = bot.getUpdates(bot.last_message_received + 1);
    }

    lastTimeBotRun = millis();
  }

  checkPIR();
}