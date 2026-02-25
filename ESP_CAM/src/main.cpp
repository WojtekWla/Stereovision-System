#include <Arduino.h>
#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include <HTTPClient.h>
#include <WebSocketsServer.h>
#include "time.h"

const char* ssid = "{{SSID}}}";
const char* password = "{{PASSWORD}}";

#define CAMERA_MODEL_AI_THINKER

#if defined(CAMERA_MODEL_AI_THINKER)
  #define PWDN_GPIO_NUM     32
  #define RESET_GPIO_NUM    -1
  #define XCLK_GPIO_NUM      0
  #define SIOD_GPIO_NUM     26
  #define SIOC_GPIO_NUM     27
  
  #define Y9_GPIO_NUM       35
  #define Y8_GPIO_NUM       34
  #define Y7_GPIO_NUM       39
  #define Y6_GPIO_NUM       36
  #define Y5_GPIO_NUM       21
  #define Y4_GPIO_NUM       19
  #define Y3_GPIO_NUM       18
  #define Y2_GPIO_NUM        5
  #define VSYNC_GPIO_NUM    25
  #define HREF_GPIO_NUM     23
  #define PCLK_GPIO_NUM     22
#else
  #error "Camera model not selected"
#endif

const u_int16_t WS_PORT = 7890;
uint8_t client = 0xFF;
uint32_t clientConnectionTime = 0L;

bool streaming = false;
uint32_t lastFrameTime = 0;

bool duringSynchronization = false;
uint32_t syncStartTime = 0;
uint32_t SYNC_TIME = 3000;
int fps_rate = 30;

WebSocketsServer ws = WebSocketsServer(WS_PORT);

void onWsEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t len) {
  switch (type) {
    case WStype_CONNECTED: {
      client = num;
      clientConnectionTime = millis();
      IPAddress ip = ws.remoteIP(num);
      Serial.printf("Client %u connected: %s\n", num, ip.toString().c_str());
      break;
    }
    case WStype_DISCONNECTED:
      Serial.printf("Client %u disconnected\n", num);
      streaming = false;
      break;
    case WStype_TEXT: {
      String cmd((char*)payload, len);
      if (cmd == "start") {
        Serial.println("Starting stream in 2 seconds");
        delay(2000);
        streaming = true;
      } else if (cmd == "sync") {
        Serial.println("Synchronizing");
        streaming = false;
        duringSynchronization = true;
        syncStartTime = millis();
      }
      break;
    }
    default: break;
  }
}

bool canTakePicture(uint32_t currentTime, uint32_t previousTime) {
  if (duringSynchronization && millis() - syncStartTime >= SYNC_TIME) {  
    duringSynchronization = false; 
    streaming = true;
  }

  return !duringSynchronization 
          && streaming 
          && currentTime - lastFrameTime >= (int)(1000/fps_rate);
}

void capturePhoto() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (fb) {
    uint32_t timeDifference = millis() - clientConnectionTime;
    const size_t timeBufferSize = 4;
    const size_t totalBufferSize = timeBufferSize + fb->len;
    uint8_t *totalBuffer = (uint8_t *)malloc(totalBufferSize);

    if (!totalBuffer) {
      Serial.println("Couldn't create buffer");
      esp_camera_fb_return(fb);
      return;
    }

    totalBuffer[0] = (timeDifference >> 24) & 0xFF;
    totalBuffer[1] = (timeDifference >> 16) & 0xFF;
    totalBuffer[2] = (timeDifference >> 8) & 0xFF;
    totalBuffer[3] = (timeDifference) & 0xFF;

    memcpy(totalBuffer + timeBufferSize, fb->buf, fb->len);
    ws.sendBIN(client, totalBuffer, totalBufferSize);
    free(totalBuffer);
    esp_camera_fb_return(fb);
  }
}

void setCameraParameters() {
  sensor_t *s = esp_camera_sensor_get();
  s->set_exposure_ctrl(s, 0);
  s->set_aec2(s, 0);
  s->set_gain_ctrl(s, 0);
  s->set_whitebal(s, 0);
  s->set_awb_gain(s, 0);

  s->set_aec_value(s, 600);   
  s->set_agc_gain(s, 4);
  s->set_gainceiling(s, GAINCEILING_4X);

  s->set_brightness(s, 0);
  s->set_contrast(s, 0);      
  s->set_saturation(s, 0);
  s->set_sharpness(s, 0);     

  s->set_lenc(s, 1);          
  s->set_bpc(s, 1);
  s->set_wpc(s, 1);
  s->set_raw_gma(s, 1);       

  
  s->set_hmirror(s, 0);
  s->set_vflip(s, 0);
}

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  Serial.setDebugOutput(false);
  Serial.println("Initializing camera...");

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_LATEST;

  config.frame_size = FRAMESIZE_SVGA;
  config.jpeg_quality = 4;
  config.fb_count = 2;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.println("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  WiFi.setSleep(false); 
  Serial.println("WiFi connected");
  Serial.print("Camera Stream Ready! Go to: ws://");
  Serial.print(WiFi.localIP());

  setCameraParameters();
  ws.begin();
  ws.onEvent(onWsEvent); 
}

void loop() {
  ws.loop();
  uint32_t now = millis();
  if(canTakePicture(now, lastFrameTime)) {
    capturePhoto();
    lastFrameTime = now;
  }
  delay(1);
}
