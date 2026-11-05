#include <Arduino.h>
#include <Encoder.h>
#include <Servo.h>

#define INPUT_PULLUP
#define ENCODER_USE_INTERRUPTS6+++++++

Encoder rodaEncoder(2, 3);

Servo myservo;
const int pinoServo = 9;

const float K = 0.51;

unsigned long lastTime = 0;
long lastTicks = 0;
const unsigned long intervalo_dt = 50;

const int N_FILTRO = 20; 
float buf[N_FILTRO] = {0};
int idx = 0;

float mediaMovel(float novaVelocidade) {
  float soma = 0;
  buf[idx] = novaVelocidade;
  idx = (idx + 1) % N_FILTRO;

  for (int i = 0; i < N_FILTRO; i++) {
    soma += buf[i];
  }
  return soma / (float)N_FILTRO;
}

void setup() {
  Serial.begin(115200);
  
  myservo.attach(pinoServo);
  myservo.writeMicroseconds(1500);

  lastTime = millis();
  lastTicks = rodaEncoder.read();
}

void loop() {
  myservo.writeMicroseconds(1700); 
  
  unsigned long currentTime = millis();
  unsigned long deltaTime = currentTime - lastTime;

  if (deltaTime >= intervalo_dt) {
    long t = rodaEncoder.read();
    long deltaTicks = t - lastTicks;

    float deltaS = deltaTicks * K; 
    
    float speedBruta = (deltaS / (float)deltaTime) * 1000.0; 

    float speedFiltrada = mediaMovel(speedBruta);

    Serial.print(speedBruta);
    Serial.print(",");
    Serial.println(speedFiltrada);

    lastTime = currentTime;
    lastTicks = t;
  }
}