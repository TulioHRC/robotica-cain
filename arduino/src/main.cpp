#include <Arduino.h>
// LED infravermelho no D8, coletor do fototransistor no A0.
// Comecem com 1 s ligado e 1 s desligado. Depois reduzam os dois.
const int PIN_LED = 8;
const int PIN_ADC = A0;
unsigned long t_on_ms = 1;
unsigned long t_off_ms = 1;
// mudar p 200, 100

void setup()
{
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);
  Serial.begin(115200);
}

void loop()
{
  digitalWrite(PIN_LED, HIGH);
  delay(t_on_ms);
  int adc_on = analogRead(PIN_ADC);
  digitalWrite(PIN_LED, LOW);
  delay(t_off_ms);
  int adc_off = analogRead(PIN_ADC);
  int sinal = adc_off - adc_on;
  if (sinal < 0)
    sinal = 0;
  Serial.println(sinal);
}