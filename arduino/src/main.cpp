#include "Arduino.h"

const int BTN = 2;
const int LED = 3;
int last = HIGH;
int on = LOW;
int counter = 0;

void setup() {
  // put your setup code here, to run once:
  pinMode(BTN, INPUT);
  pinMode(LED, OUTPUT);
  Serial.begin(115200);
  Serial.println("Mega: D2 botao, D3 LED");
}

void loop() {
  // put your main code here, to run repeatedly:
  int now = digitalRead(BTN);

  if (last == HIGH && now == LOW) {
    counter++;

    if (counter == 5) {
      counter = 0;
    }
  }

  if (counter > 0) {
    Serial.println("Ligando LED");
    digitalWrite(LED, HIGH);
    delay(5);
    Serial.print("Sleeping for ");
    Serial.println("Desligando LED");
    digitalWrite(LED, LOW);
    Serial.println(50 * counter / 5);
    delay(50 * counter / 5);
  }

  last = now;
}
