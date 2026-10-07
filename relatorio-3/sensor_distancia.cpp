#include <Arduino.h>
// LED infravermelho no D8, coletor do fototransistor no A0.
// Comecem com 1 s ligado e 1 s desligado. Depois reduzam os dois.
const int PIN_LED = 8;
const int PIN_ADC = A0;
unsigned long t_on_ms = 1000;
unsigned long t_off_ms = 1000;
// mudar p 200, 100

// Ganhos da planilha (regressão de 30 a 100 mm): d = g0 + g1 / sqrt(S)
const float G0 = 10.976;   // mm
const float G1 = 283.703;  // mm·√contagem

// S = 0: sinal abaixo de 1 contagem -> alvo além do ponto em que S = 1,
// ou seja, d >= G0 + G1 ≈ 294.7 mm. Imprime esse limite, sem dividir por zero.
const float D_MAX = G0 + G1;

float distancia_mm(int s)
{
  if (s <= 0)
    return D_MAX;
  return G0 + G1 / sqrt((float)s);
}

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

  // sinal,mm
  Serial.print(sinal);
  Serial.print(',');
  Serial.println(distancia_mm(sinal), 1);
}
