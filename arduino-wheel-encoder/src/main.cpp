// =============================================================
//  Roda HeRo: SG90 continuo + encoder + PID de velocidade
//  Arduino Mega: servo no D9, encoder A/B no D3 e D2 (trocados)
//
//  Comandos (use com registrar.py, final de linha "Nova linha"):
//    v 100     -> degrau de velocidade em mm/s (sintonia), por 6 s e para sozinho.
//    v 100 8   -> idem, por 8 s. Negativo = outro sentido.
//    1         -> ensaio 1: cinco patamares crescentes
//    2         -> ensaio 2: inversao de sentido (+v e depois -v)
//    s         -> para antes da hora (todos os ensaios terminam sozinhos)
//    kp 1.0    -> muda kp   (idem ki, kd)
//    neutro 1495 -> muda o neutro (us)
//    b 30      -> muda a meia-largura da banda morta (us)
//    ?         -> mostra a configuracao atual
//
//  Cada ensaio sai entre "INICIO <nome>" e "FIM", em CSV:
//    t_ms,ticks,s_mm,setpoint,v_bruta,v_filtrada,u_us,pulso_us
// =============================================================
#include <Arduino.h>
#include <Encoder.h>
#include <Servo.h>

// ---------- Hardware ----------
// A e B trocados (3, 2): sem isso a contagem vem com sinal oposto ao do pulso.
Encoder enc(3, 2);
Servo servo;
const int PIN_SERVO = 9;

// ---------- Valores medidos pela equipe ----------
const float K_MM_POR_TICK = 0.513; // k = pi * D / N  (D = 40 mm, N = 245)
int NEUTRO_US      = 1495;         // da busca do neutro (comando n do malha_aberta)
int BANDA_MORTA_US = 30;           // meia-largura da banda morta (parada de 1470 a 1520)

// ---------- PID (comecam em P puro; sintonize um ganho por vez) ----------
float kp = 1.0, ki = 0.0, kd = 0.0;
const float U_MAX = 250.0;           // correcao limitada a +-250 us em torno do neutro
const float ALPHA = 0.3;             // passa-baixa escolhido na comparacao de filtros
const unsigned long PERIODO_MS = 50; // periodo do controle (o codigo usa o dt REAL)

// ---------- Ensaios ----------
const float PAT_VEL[5] = {90, 105, 120, 135, 150}; // mm/s, dentro da curva medida
const unsigned long PAT_DUR = 3000;                // ms por patamar
const float INV_VEL = 100;                         // mm/s
const unsigned long INV_DUR = 4000;                // ms em cada sentido
const unsigned long PRE_MS = 1000;                 // repouso antes do primeiro degrau
const unsigned long POS_MS = 2000;                 // repouso no fim
const unsigned long MANUAL_DUR_MS = 6000;          // duracao padrao do comando v (apos o repouso)

// ---------- Estado ----------
enum Modo { PARADO, MANUAL, PATAMARES, INVERSAO };
Modo modo = PARADO;

unsigned long tAntUs = 0, tInicio = 0;
long  ticks0 = 0, ticksAnt = 0;
float vFilt = 0, vFiltAnt = 0;
float sp = 0, spManual = 0;
unsigned long manualDur = MANUAL_DUR_MS;
float integral = 0;

// -------------------------------------------------------------
void imprimirConfig() {
  Serial.print(F("# neutro_us=")); Serial.print(NEUTRO_US);
  Serial.print(F(" banda_us=")); Serial.print(BANDA_MORTA_US);
  Serial.print(F(" k_mm_tick=")); Serial.print(K_MM_POR_TICK, 4);
  Serial.print(F(" periodo_ms=")); Serial.print(PERIODO_MS);
  Serial.print(F(" alpha=")); Serial.print(ALPHA, 3);
  Serial.print(F(" kp=")); Serial.print(kp, 3);
  Serial.print(F(" ki=")); Serial.print(ki, 3);
  Serial.print(F(" kd=")); Serial.println(kd, 3);
}

void parar() {
  servo.writeMicroseconds(NEUTRO_US);
  if (modo != PARADO) {
    modo = PARADO;
    Serial.println(F("FIM"));
  }
  sp = 0;
  integral = 0;
}

void iniciar(Modo m, const __FlashStringHelper *nome) {
  if (modo != PARADO) parar();             // fecha o ensaio anterior (imprime FIM)
  modo = m;
  tInicio = millis();
  ticks0 = ticksAnt = enc.read();
  vFilt = vFiltAnt = 0;
  integral = 0;
  sp = 0;
  tAntUs = micros();
  Serial.print(F("INICIO ")); Serial.println(nome);
  imprimirConfig();
  Serial.println(F("t_ms,ticks,s_mm,setpoint,v_bruta,v_filtrada,u_us,pulso_us"));
}

float setpointDoEnsaio(unsigned long t) {
  switch (modo) {
    case MANUAL:
      return (t < PRE_MS) ? 0 : spManual;
    case PATAMARES: {
      if (t < PRE_MS) return 0;
      unsigned long k = (t - PRE_MS) / PAT_DUR;
      return (k < 5) ? PAT_VEL[k] : 0;
    }
    case INVERSAO:
      if (t < PRE_MS) return 0;
      if (t < PRE_MS + INV_DUR) return INV_VEL;
      if (t < PRE_MS + 2 * INV_DUR) return -INV_VEL;
      return 0;
    default:
      return 0;
  }
}

bool ensaioAcabou(unsigned long t) {
  if (modo == MANUAL)    return t > PRE_MS + manualDur + POS_MS;
  if (modo == PATAMARES) return t > PRE_MS + 5 * PAT_DUR + POS_MS;
  if (modo == INVERSAO)  return t > PRE_MS + 2 * INV_DUR + POS_MS;
  return false;
}

// -------------------------------------------------------------
void tratarComando(char *linha) {
  char *cmd = strtok(linha, " ");
  if (!cmd) return;
  char *arg = strtok(NULL, " ");
  char *arg2 = strtok(NULL, " ");
  float x = arg ? atof(arg) : 0;

  if      (!strcmp(cmd, "1"))  iniciar(PATAMARES, F("patamares"));
  else if (!strcmp(cmd, "2"))  iniciar(INVERSAO, F("inversao"));
  else if (!strcmp(cmd, "v"))  { spManual = x;
                                 manualDur = arg2 ? (unsigned long)(atof(arg2) * 1000) : MANUAL_DUR_MS;
                                 iniciar(MANUAL, F("manual")); }
  else if (!strcmp(cmd, "s"))  parar();
  else if (!strcmp(cmd, "kp")) { kp = x; imprimirConfig(); }
  else if (!strcmp(cmd, "ki")) { ki = x; integral = 0; imprimirConfig(); }
  else if (!strcmp(cmd, "kd")) { kd = x; imprimirConfig(); }
  else if (!strcmp(cmd, "neutro")) { NEUTRO_US = (int)x; if (modo == PARADO) servo.writeMicroseconds(NEUTRO_US); imprimirConfig(); }
  else if (!strcmp(cmd, "b"))  { BANDA_MORTA_US = (int)x; imprimirConfig(); }
  else if (!strcmp(cmd, "?"))  imprimirConfig();
  else Serial.println(F("# comando desconhecido"));
}

void lerSerial() {
  static char buf[32];
  static byte n = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (n) { buf[n] = 0; tratarComando(buf); n = 0; }
    } else if (n < sizeof(buf) - 1) {
      buf[n++] = c;
    }
  }
}

// -------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  servo.attach(PIN_SERVO);
  servo.writeMicroseconds(NEUTRO_US);
  Serial.println(F("# pronto. Comandos: v <mm/s> [s], 1, 2, s, kp/ki/kd <x>, neutro <us>, b <us>, ?"));
  imprimirConfig();
}

void loop() {
  lerSerial();
  if (modo == PARADO) return;

  // Controle em periodo fixo, sem delay()
  unsigned long agoraUs = micros();
  if (agoraUs - tAntUs < PERIODO_MS * 1000UL) return;
  float dt = (agoraUs - tAntUs) * 1e-6;   // dt REAL entre leituras
  tAntUs = agoraUs;

  // Encoder -> distancia -> velocidade
  long ticks = enc.read();
  long dTicks = ticks - ticksAnt;
  ticksAnt = ticks;

  float vBruta = dTicks * K_MM_POR_TICK / dt;
  vFiltAnt = vFilt;
  vFilt = ALPHA * vBruta + (1 - ALPHA) * vFilt;

  long tk = ticks - ticks0;
  float sMm = tk * K_MM_POR_TICK;
  unsigned long t = millis() - tInicio;

  // Setpoint; zera a integral quando ele muda (para nao carregar o erro antigo)
  float novoSp = setpointDoEnsaio(t);
  if (novoSp != sp) { sp = novoSp; integral = 0; }

  float u = 0;
  if (sp != 0) {
    float erro = sp - vFilt;

    integral += erro * dt;
    if (ki > 0) {                            // a integral tem limite
      float iMax = U_MAX / ki;
      integral = constrain(integral, -iMax, iMax);
    }

    float deriv = -(vFilt - vFiltAnt) / dt;  // derivada da MEDIDA filtrada, nao do erro

    // Compensacao que pula a banda morta no sentido certo
    float ff = (sp > 0) ? BANDA_MORTA_US : -BANDA_MORTA_US;

    u = ff + kp * erro + ki * integral + kd * deriv;
    u = constrain(u, -U_MAX, U_MAX);         // correcao em +-250 us
  } else {
    integral = 0;                            // setpoint zero: neutro, roda parada
  }

  int pulso = constrain(NEUTRO_US + (int)u, 1000, 2000);
  servo.writeMicroseconds(pulso);

  // Registro (CSV)
  Serial.print(t);          Serial.print(',');
  Serial.print(tk);         Serial.print(',');
  Serial.print(sMm, 2);     Serial.print(',');
  Serial.print(sp, 1);      Serial.print(',');
  Serial.print(vBruta, 2);  Serial.print(',');
  Serial.print(vFilt, 2);   Serial.print(',');
  Serial.print(u, 1);       Serial.print(',');
  Serial.println(pulso);

  if (ensaioAcabou(t)) parar();
}
