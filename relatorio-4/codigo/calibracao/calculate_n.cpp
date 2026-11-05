#include <Encoder.h>

Encoder rodaEncoder(2, 3);

long posicaoAntiga = -999999;

void setup() {
  Serial.begin(115200);
  Serial.println("Gire a roda exatamente uma volta (360 graus) e anote o valor final:");
}

void loop() {
  long posicaoAtual = rodaEncoder.read();
  
  if (posicaoAtual != posicaoAntiga) {
    Serial.print("Ticks: ");
    Serial.println(posicaoAtual);
    posicaoAntiga = posicaoAtual;
  }
}