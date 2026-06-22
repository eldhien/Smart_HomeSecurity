#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <UniversalTelegramBot.h>
#include <ArduinoJson.h>
#include "DHT.h"


const char* ssid = "Usernamw_wifi";
const char* password = "password_wifi";

#define BOTtoken "Token_Bot"
#define CHAT_ID "Chat_ID"


#define DHTPIN 12
#define DHTTYPE DHT22

#define IR_PIN 14
#define PIR_PIN 27
#define LDR_PIN 16

DHT dht(DHTPIN, DHTTYPE);
WiFiClientSecure client;
UniversalTelegramBot bot(BOTtoken, client);

unsigned long lastTimeBotRun = 0;
unsigned long botInterval = 1000;

unsigned long lastPirAlert = 0;
const long pirCooldown = 15000; 

bool lastPirState = LOW;

void connectWiFi() {
  Serial.print("Connecting to WiFi...");
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nConnected!");
  Serial.println(WiFi.localIP());
}

String getStatusReport() {
  float temp = dht.readTemperature();
  float hum = dht.readHumidity();

  int irState = digitalRead(IR_PIN);
  int ldrState = digitalRead(LDR_PIN);

  String lampu = (ldrState == LOW) ? "HIDUP" : "MATI";
  String orang = (irState == LOW) ? "ADA ORANG DI PINTU" : "AREA KOSONG";

  String report = "📊 STATUS RUANGAN SAAT INI\n";
  report += "💡 Kondisi Lampu: " + lampu + "\n";
  report += "🚶 Keberadaan Orang: " + orang + "\n";
  report += "🌡️ Suhu: " + String(temp) + " °C\n";
  report += "💧 Kelembaban: " + String(hum) + " %\n";

  return report;
}

void handleNewMessages(int numNewMessages) {
  for (int i = 0; i < numNewMessages; i++) {

    String chat_id = bot.messages[i].chat_id;
    String text = bot.messages[i].text;

    if (text == "/status") {
      String report = getStatusReport();
      bot.sendMessage(chat_id, report, "");
    }
  }
}

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

void setup() {
  Serial.begin(115200);

  pinMode(IR_PIN, INPUT);
  pinMode(PIR_PIN, INPUT);
  pinMode(LDR_PIN, INPUT);

  dht.begin();

  connectWiFi();

  client.setInsecure(); 

  Serial.println("System Ready!");
}


void loop() {

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