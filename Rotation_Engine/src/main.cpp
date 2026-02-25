#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <WebSocketsServer.h>

const char* ssid = "{{SSID}}";
const char* password = "{{PASSWORD}}";

const int DIR_LATCH = 19;
const int DIR_CLK   = 17;
const int DIR_SER   = 12;
const int DIR_EN    = 14; 

const int M1_PWM = 23;
const int M2_PWM = 25;
const int M3_PWM = 27;
const int M4_PWM = 16;

#define WS_PORT 80 

int shiftRegisterState = 0;

WebSocketsServer ws = WebSocketsServer(WS_PORT);
uint8_t connectedClient = 0xFF;

void writeShiftRegister(int data);
void controlMotor(int motorID, String direction, int speed);
void stopAll();
void wsOnEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t len);

enum RotationDirection {
  UP,
  DOWN,
  RIGHT,
  LEFT,
  ALLL,
  ALLR
};

class RotationController {
  private:
    bool rotating = false;
    int rotationSpeed = 255;
    int armRotationSpeed = 125;    

  public:
    void rotate(RotationDirection rotationDirection) {
      if (rotating) {
        rotating = false;
        stop();
      }
      switch (rotationDirection)
      {
      case UP:
        rotating = true;
        Serial.println("Starting rotation up");
        controlMotor(2, "BACKWARD", rotationSpeed);
        controlMotor(3, "FORWARD", rotationSpeed);
        break;
      case DOWN:
        rotating = true;
        Serial.println("Starting rotation down");
        controlMotor(2, "BACKWARD", rotationSpeed);
        controlMotor(3, "BACKWARD", rotationSpeed);
        break;
      case RIGHT:
        Serial.println("Starting rotation to the right");
        controlMotor(1, "BACKWARD", rotationSpeed);
        controlMotor(2, "BACKWARD", rotationSpeed);
        controlMotor(3, "FORWARD", rotationSpeed);
        controlMotor(4, "BACKWARD", rotationSpeed);

        rotating = true;
        break;  
      case LEFT:
        Serial.println("Starting rotation to the left");
        controlMotor(1, "FORWARD", rotationSpeed);
        controlMotor(2, "BACKWARD", rotationSpeed);
        controlMotor(3, "BACKWARD", rotationSpeed);
        controlMotor(4, "BACKWARD", rotationSpeed);
        rotating = true;
        break;
      case ALLL:
        Serial.println("Starting rotation all to the left");
        controlMotor(1, "FORWARD", rotationSpeed);
        controlMotor(2, "FORWARD", rotationSpeed);
        controlMotor(3, "FORWARD", rotationSpeed);
        controlMotor(4, "FORWARD",rotationSpeed);
        break;
      case ALLR:
        Serial.println("Starting rotation all to the right");
        controlMotor(1, "BACKWARD", rotationSpeed);
        controlMotor(2, "BACKWARD", rotationSpeed);
        controlMotor(3, "BACKWARD", rotationSpeed);
        controlMotor(4, "BACKWARD", rotationSpeed);
        break;
      default:
        break;
      }
    }

    void stop() {
      Serial.println("Stopping rotation");
      controlMotor(1, "RELEASE", 0);
      controlMotor(2, "RELEASE", 0);
      controlMotor(3, "RELEASE", 0);
      controlMotor(4, "RELEASE", 0);
    }
};

RotationController rotationController;

void setup() {
  Serial.begin(115200);
  Serial.println("Initializing 4-Motor Control...");

  pinMode(DIR_LATCH, OUTPUT);
  pinMode(DIR_CLK, OUTPUT);
  pinMode(DIR_SER, OUTPUT);
  pinMode(DIR_EN, OUTPUT);

  pinMode(M1_PWM, OUTPUT);
  pinMode(M2_PWM, OUTPUT);
  pinMode(M3_PWM, OUTPUT);
  pinMode(M4_PWM, OUTPUT);

  digitalWrite(DIR_EN, LOW); 

  shiftRegisterState = 0;
  writeShiftRegister(shiftRegisterState);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  while(WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("WiFi connected");
  Serial.print("Rotation engine server ready! Go to: ws://");
  Serial.print(WiFi.localIP());

  rotationController = RotationController();
  ws.begin();
  ws.onEvent(wsOnEvent);
}

void loop() {
  ws.loop();
  delay(1);
}

void controlMotor(int motorID, String direction, int speed) {
  int a, b;
  int pwmPin;

  switch (motorID) {
    case 1: a = 2; b = 3; pwmPin = M1_PWM; break;
    case 2: a = 1; b = 4; pwmPin = M2_PWM; break;
    case 3: a = 5; b = 7; pwmPin = M3_PWM; break;
    case 4: a = 0; b = 6; pwmPin = M4_PWM; break;
    default: return;
  }

  if (direction == "FORWARD") {
    bitSet(shiftRegisterState, a);
    bitClear(shiftRegisterState, b);
  } else if (direction == "BACKWARD") {
    bitClear(shiftRegisterState, a);
    bitSet(shiftRegisterState, b);
  } else {
    bitClear(shiftRegisterState, a);
    bitClear(shiftRegisterState, b);
    speed = 0;
  }

  writeShiftRegister(shiftRegisterState);

  analogWrite(pwmPin, speed);
}


void writeShiftRegister(int data) {
  digitalWrite(DIR_LATCH, LOW);
  shiftOut(DIR_SER, DIR_CLK, MSBFIRST, data); 
  digitalWrite(DIR_LATCH, HIGH);
}  

void wsOnEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t len) {
  switch (type) {
    case WStype_CONNECTED: {
      connectedClient = num;
      IPAddress ip = ws.remoteIP(num);
      Serial.printf("Client %u connected: %s\n", num, ip.toString().c_str());
      break;
    }
    case WStype_DISCONNECTED:
      Serial.printf("Client %u disconnected\n", num);
      rotationController.stop();
      break;
    case WStype_TEXT: {
      String cmd((char*)payload, len);
      Serial.println("Received command");
      Serial.println(cmd);
      if (cmd == "left") {
        rotationController.rotate(LEFT);
        ws.sendTXT(num, "Rotating left");
      } else if (cmd == "right") {
        rotationController.rotate(RIGHT);
        ws.sendTXT(num, "Rotating right");
      }else if(cmd == "up") {
        rotationController.rotate(UP);
        ws.sendTXT(num, "Rotating up");
      }else if(cmd == "down") {
        rotationController.rotate(DOWN);
        ws.sendTXT(num, "Rotating down");
      }else if(cmd == "stop") {
        rotationController.stop();
        ws.sendTXT(num, "stop");
      }else if(cmd == "alll") {
        rotationController.rotate(ALLL);
        ws.sendTXT(num, "alll");
      }else if(cmd == "allr") {
        rotationController.rotate(ALLR);
        ws.sendTXT(num, "allr");
      }
      break;
    }
    default: break;
  }
}
