#include <Arduino.h>
#include <Encoder.h>

// Definição dos pinos do encoder (ajuste para os pinos do seu robô)
#define ENC_A 2
#define ENC_B 3

Encoder myEnc(ENC_A, ENC_B);

long posicaoAntiga  = -999;

void setup() {
  Serial.begin(115200);
  Serial.println("--- Calibrador de Ticks por Volta ---");
  Serial.println("1. Faca uma marca na roda e no chassi do robo.");
  Serial.println("2. Envie 'r' no Monitor Serie para zerar o contador.");
  Serial.println("3. Gire a roda manualmente exatamente 1 volta completa.");
  Serial.println("4. O valor final no ecra e o seu N (ticks por volta).");
}

void loop() {
  // Verifica se o utilizador enviou o comando de reset
  if (Serial.available() > 0) {
    char comando = Serial.read();
    if (comando == 'r' || comando == 'R') {
      myEnc.write(0); // Repõe o contador a zero
      Serial.println("\nContador reposto a ZERO!");
    }
  }

  // Lê a posição atual
  long posicaoAtual = myEnc.read();

  // Imprime apenas se o valor mudar
  if (posicaoAtual != posicaoAntiga) {
    Serial.print("Ticks atuais: ");
    Serial.println(posicaoAtual);
    posicaoAntiga = posicaoAtual;
  }
}