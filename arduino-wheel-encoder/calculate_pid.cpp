#include <Arduino.h>
#include <Encoder.h>
#include <Servo.h>

Encoder myEnc(2, 3);
Servo myservo;

const int   NEUTRO = 1500;         // pulso em que a roda para
const float K_MM_POR_TICK = -0.51;  // k = pi*D/N

// ---- PID ----
float kp = 1.5, ki = 2.0, kd = 0.0;
const float U_MAX = 250;           // +-250 us em torno do neutro
const unsigned long PERIODO_MS = 100;
const float ALPHA = 0.3;           // filtro da velocidade

float setpoint = 150;              // mm/s 
float integral = 0;
float vFilt = 0, vFiltAnt = 0;

unsigned long lastUs;
long lastTicks = 0;

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(20);
  myservo.attach(9);
  myservo.writeMicroseconds(NEUTRO);
  lastTicks = myEnc.read();
  lastUs = micros();
}

void loop() {
  if (Serial.available()) {
    float sp = Serial.parseFloat();
    while (Serial.available()) Serial.read();
    setpoint = sp;
    integral = 0;                      // zera a integral ao mudar o setpoint
  }

  unsigned long agora = micros();
  if (agora - lastUs < PERIODO_MS * 1000UL) return;

  float dt = (agora - lastUs) / 1e6;   // dt real entre leituras
  lastUs = agora;

  long t = myEnc.read();
  long dTicks = t - lastTicks;
  lastTicks = t;

  // Velocidade medida e filtrada
  float vBruta = dTicks * K_MM_POR_TICK / dt;
  vFiltAnt = vFilt;
  vFilt = ALPHA * vBruta + (1 - ALPHA) * vFilt;

  // ---- PID ----
  float u = 0;
  if (setpoint != 0) {
    float erro = setpoint - vFilt;

    integral += erro * dt;
    if (ki > 0) integral = constrain(integral, -U_MAX / ki, U_MAX / ki); // anti-windup

    float deriv = -(vFilt - vFiltAnt) / dt;  // derivada da medida, não do erro

    u = kp * erro + ki * integral + kd * deriv;
    u = constrain(u, -U_MAX, U_MAX);
  } else {
    integral = 0;
  }

  int pulso = constrain(NEUTRO + (int)u, 1000, 2000);
  myservo.writeMicroseconds(pulso);

  Serial.print("setpoint:");    Serial.print(setpoint);
  Serial.print(" velocidade:"); Serial.print(vFilt);
  Serial.print(" bruta:");      Serial.print(vBruta);
  Serial.print(" pulso:");      Serial.println(pulso - NEUTRO);
}