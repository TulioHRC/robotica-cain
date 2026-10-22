#include <Arduino.h>
#include <Encoder.h>
#include <Servo.h>

// Instancia o encoder informando os pinos A e B
Encoder myEnc(2, 3);

const int N = 5;
int buf[N] = {0, 0, 0, 0, 0};
int idx = 0;

Servo myservo;

// Média móvel
double sma(int newValue) {
  int sum = 0;

  buf[idx] = newValue;
  idx = (idx + 1) % N;

  for (int i = 0; i < N; i++) {
    sum += buf[i];
  }

  return (double)sum / (double)N;
}

// Filtro Passa baixa
double lowPass(int newValue, double alpha) {
  static double filteredValue = 0;
  filteredValue = alpha * newValue + (1 - alpha) * filteredValue;
  return filteredValue;
}

unsigned long lastTime;
unsigned long currentTime;
long lastTicks = 0;

void setup() {
  Serial.begin(115200);
   
  myservo.attach(9);

  lastTime = millis();
}

void loop() {
  myservo.writeMicroseconds(500);

  long t = myEnc.read();

  currentTime = millis();

  long deltaTime = currentTime - lastTime;
  long deltaTicks = t - lastTicks;
  
  float speed = 0.0;
  if (deltaTime > 0) {
    speed = ((float)deltaTicks / (float)deltaTime) * 0.54 * 1000; // mm por s
  }

  Serial.print("ticks: ");
  Serial.print(t);

  Serial.print(" | Last ticks: ");
  Serial.println(lastTicks);

  Serial.print("Velocidade: ");
  Serial.print(speed);
  Serial.println(" mm/s");

  lastTime = currentTime;
  lastTicks = t;
  
  delay(500);

  // Testes de filtro (se quiser usar os filtros, lembre de passar myEnc.read())
  // Serial.println(myEnc.read());
  // Serial.println(lowPass(myEnc.read(), 0.5));
}