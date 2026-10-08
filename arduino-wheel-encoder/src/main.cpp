#include <Arduino.h>
#include <Servo.h>

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

volatile long ticks = 0;
// last time of tick
unsigned long lastTime;
unsigned long currentTime;
volatile long lastTicks = 0;

void isrA() { if (digitalRead(2) == digitalRead(3)) ticks--; else ticks++; }
void isrB() { if (digitalRead(2) == digitalRead(3)) ticks++; else ticks--; }

void setup() {
  Serial.begin(115200);
  pinMode(2, INPUT_PULLUP);
  pinMode(3, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(2), isrA, CHANGE);
  attachInterrupt(digitalPinToInterrupt(3), isrB, CHANGE);

  myservo.attach(9);

  lastTime = millis();
}

long lerTicks() { noInterrupts(); long t = ticks; interrupts(); return t; }

void loop() {
  myservo.writeMicroseconds(1000);

  long t = lerTicks();
  currentTime = millis();

  // calcular velocidade instantanea
  long deltaTime = currentTime - lastTime;
  long deltaTicks = t - lastTicks;
  float speed = ((float)deltaTicks / (float)deltaTime) * 0.54 * 60.0; // ticks por minuto

  Serial.print("ticks: ");
  Serial.print(t);

  Serial.print(" | Last ticks: ");
  Serial.println(lastTicks);

  Serial.print("Velocidade: ");
  Serial.print(speed);
  Serial.println(" ticks/min");

  lastTime = currentTime;
  lastTicks = t;
  delay(50);


  // Serial.println(lerTicks());
  // Serial.println(lowPass(lerTicks(), 0.5));
}