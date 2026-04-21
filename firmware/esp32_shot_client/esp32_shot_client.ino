/**
 * ESP32 — WebSocket client sending SHOT_EVENT JSON to Project ONYX FastAPI.
 *
 * Library: "WebSockets" by Markus Sattler (Arduino Library Manager: "WebSockets").
 * Board: ESP32 Arduino core.
 *
 * Set YOUR_WIFI_*, BACKEND_HOST, SESSION_ID, then open Serial Monitor (115200).
 */

#include <WiFi.h>
#include <WebSocketsClient.h>

// ---- WiFi ----
const char *WIFI_SSID = "YOUR_WIFI_SSID";
const char *WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// ---- Backend (same LAN as ESP32; use your PC's IP if running uvicorn locally) ----
const char *BACKEND_HOST = "192.168.1.100";  // no "http://"
const uint16_t BACKEND_PORT = 8000;

// Session UUID from POST /api/sessions (browser or curl)
const char *SESSION_ID = "00000000-0000-0000-0000-000000000000";

WebSocketsClient webSocket;

static void sendShotEvent() {
  uint64_t ts = (uint64_t)millis();
  char json[512];
  snprintf(
      json, sizeof(json),
      "{"
      "\"type\":\"SHOT_EVENT\","
      "\"shot_type\":\"Forehand\","
      "\"confidence\":0.85,"
      "\"device_ts_ms\":%llu,"
      "\"accel_x\":0.1,\"accel_y\":0.2,\"accel_z\":9.8,"
      "\"gyro_x\":0.0,\"gyro_y\":0.0,\"gyro_z\":0.0"
      "}",
      (unsigned long long)ts);

  webSocket.sendTXT(json);
  Serial.println("Sent SHOT_EVENT");
}

static void onWebSocketEvent(WStype_t type, uint8_t *payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      Serial.println("[WS] disconnected");
      break;
    case WStype_CONNECTED:
      Serial.printf("[WS] connected: %s\n", payload);
      break;
    case WStype_ERROR:
      Serial.println("[WS] error");
      break;
    case WStype_TEXT:
      Serial.printf("[WS] text: %.*s\n", (int)length, (char *)payload);
      break;
    default:
      break;
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println();
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  char path[96];
  snprintf(path, sizeof(path), "/ws/shots/%s", SESSION_ID);

  webSocket.begin(BACKEND_HOST, BACKEND_PORT, path);
  webSocket.onEvent(onWebSocketEvent);
  webSocket.setReconnectInterval(3000);
  webSocket.enableHeartbeat(15000, 3000, 2);
}

void loop() {
  webSocket.loop();

  // Demo: send a shot every 5s while connected (remove in production; trigger from your MPU6050 logic)
  static uint32_t last = 0;
  if (WiFi.status() == WL_CONNECTED && webSocket.isConnected() && millis() - last > 5000) {
    last = millis();
    sendShotEvent();
  }
}
