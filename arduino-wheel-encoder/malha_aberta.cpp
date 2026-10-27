//  Comandos:
//    n            -> busca do neutro: 1400 a 1600 us em passos de 10 us
//    c            -> curva pulso x velocidade: 1000 a 2000 us, nos dois sentidos
//    f 1600       -> degrau em malha aberta com o pulso dado, comparando os 2 filtros
//    p 1550       -> pulso fixo (para testar à mão)
//    neutro 1490  -> grava o neutro medido (use depois do 'n')
//    s            -> para (manda o neutro)
#include <Arduino.h>
#include <Encoder.h>
#include <Servo.h>

Encoder enc(2, 3);
Servo servo;
const int PIN_SERVO = 9;

const float K_MM_POR_TICK = 0.51;  // k = pi*D/N
int NEUTRO_US = 1500;

// ---------- Amostragem e filtros ----------
const unsigned long PERIODO_MS = 50; // dt nominal (o código usa o dt REAL)
const int   JANELA_MEDIA = 5;        // média móvel: 5 amostras
const float ALPHA = 0.3;             // passa-baixa: v = a*bruta + (1-a)*v

// ---------- Varreduras ----------
const int NEU_MIN = 1400, NEU_MAX = 1600, NEU_PASSO = 10;
const int CUR_MIN = 1000, CUR_MAX = 2000, CUR_PASSO = 20;
const unsigned long ACOMODA_MS = 800;  // descarta o transitório
const unsigned long MEDE_MS = 1200;    // janela de medida em regime

// ---------- Degrau dos filtros ----------
const unsigned long DEG_PRE = 1000, DEG_DUR = 4000, DEG_POS = 2000;

// ---------- Estado ----------
enum Modo { PARADO, VARRE, DEGRAU, FIXO };
Modo modo = PARADO;

int vMax, vPasso, vPulso;
unsigned long vT0, vTmed;
long vTicks0;
bool vMedindo;

int degPulso;
unsigned long degT0, tAntUs;
long ticksAnt, ticks0;
float bufMedia[JANELA_MEDIA];
int idxMedia = 0, nMedia = 0;
float vPB = 0;

void imprimirConfig() {
  Serial.print(F("# k_mm_tick=")); Serial.print(K_MM_POR_TICK, 4);
  Serial.print(F(" neutro_us=")); Serial.print(NEUTRO_US);
  Serial.print(F(" periodo_ms=")); Serial.print(PERIODO_MS);
  Serial.print(F(" janela_media=")); Serial.print(JANELA_MEDIA);
  Serial.print(F(" alpha=")); Serial.println(ALPHA, 3);
}

void fim() {
  modo = PARADO;
  servo.writeMicroseconds(NEUTRO_US);
  Serial.println(F("FIM"));
}

void iniciarVarredura(const char *nome, int mn, int mx, int passo) {
  modo = VARRE;
  vMax = mx; vPasso = passo; vPulso = mn;
  vT0 = millis(); vMedindo = false;
  servo.writeMicroseconds(vPulso);
  Serial.print(F("INICIO ")); Serial.println(nome);
  imprimirConfig();
  Serial.println(F("pulso_us,ticks,dt_s,v_mm_s"));
}

void iniciarDegrau(int pulso) {
  modo = DEGRAU;
  degPulso = constrain(pulso, 1000, 2000);
  degT0 = millis();
  tAntUs = micros();
  ticks0 = ticksAnt = enc.read();
  idxMedia = 0; nMedia = 0; vPB = 0;
  servo.writeMicroseconds(NEUTRO_US);
  Serial.println(F("INICIO filtros"));
  imprimirConfig();
  Serial.print(F("# pulso_degrau_us=")); Serial.println(degPulso);
  Serial.println(F("t_ms,ticks,s_mm,dt_ms,v_bruta,v_media,v_passabaixa,pulso_us"));
}

// Mantém cada pulso, descarta o transitório e mede a velocidade em regime
void passoVarredura() {
  unsigned long agora = millis();
  unsigned long tp = agora - vT0;

  if (!vMedindo && tp >= ACOMODA_MS) {
    vTicks0 = enc.read();
    vTmed = agora;
    vMedindo = true;
  }
  if (vMedindo && tp >= ACOMODA_MS + MEDE_MS) {
    long dTicks = enc.read() - vTicks0;
    float dt = (agora - vTmed) / 1000.0;
    float v = dTicks * K_MM_POR_TICK / dt;

    Serial.print(vPulso); Serial.print(',');
    Serial.print(dTicks); Serial.print(',');
    Serial.print(dt, 3);  Serial.print(',');
    Serial.println(v, 2);

    vPulso += vPasso;
    if (vPulso > vMax) { fim(); return; }
    servo.writeMicroseconds(vPulso);
    vT0 = agora;
    vMedindo = false;
  }
}

// Degrau em malha aberta: bruta, média móvel e passa-baixa no mesmo registro
void passoDegrau() {
  unsigned long agoraUs = micros();
  if (agoraUs - tAntUs < PERIODO_MS * 1000UL) return;
  float dt = (agoraUs - tAntUs) * 1e-6;
  tAntUs = agoraUs;

  long ticks = enc.read();
  long dTicks = ticks - ticksAnt;
  ticksAnt = ticks;

  float vBruta = dTicks * K_MM_POR_TICK / dt;

  // Filtro 1: média móvel
  bufMedia[idxMedia] = vBruta;
  idxMedia = (idxMedia + 1) % JANELA_MEDIA;
  if (nMedia < JANELA_MEDIA) nMedia++;
  float soma = 0;
  for (int i = 0; i < nMedia; i++) soma += bufMedia[i];
  float vMedia = soma / nMedia;

  // Filtro 2: passa-baixa de 1ª ordem
  vPB = ALPHA * vBruta + (1 - ALPHA) * vPB;

  unsigned long t = millis() - degT0;
  int pulso = (t >= DEG_PRE && t < DEG_PRE + DEG_DUR) ? degPulso : NEUTRO_US;
  servo.writeMicroseconds(pulso);

  long tk = ticks - ticks0;
  Serial.print(t);                       Serial.print(',');
  Serial.print(tk);                      Serial.print(',');
  Serial.print(tk * K_MM_POR_TICK, 2);   Serial.print(',');
  Serial.print(dt * 1000.0, 2);          Serial.print(',');
  Serial.print(vBruta, 2);               Serial.print(',');
  Serial.print(vMedia, 2);               Serial.print(',');
  Serial.print(vPB, 2);                  Serial.print(',');
  Serial.println(pulso);

  if (t > DEG_PRE + DEG_DUR + DEG_POS) fim();
}

void tratarComando(char *linha) {
  char *cmd = strtok(linha, " ");
  if (!cmd) return;
  char *arg = strtok(NULL, " ");
  int x = arg ? atoi(arg) : 0;

  if      (!strcmp(cmd, "n")) iniciarVarredura("neutro", NEU_MIN, NEU_MAX, NEU_PASSO);
  else if (!strcmp(cmd, "c")) iniciarVarredura("curva", CUR_MIN, CUR_MAX, CUR_PASSO);
  else if (!strcmp(cmd, "f")) iniciarDegrau(arg ? x : NEUTRO_US + 100);
  else if (!strcmp(cmd, "p")) { modo = FIXO; servo.writeMicroseconds(constrain(x, 1000, 2000));
                                Serial.print(F("# pulso fixo ")); Serial.println(x); }
  else if (!strcmp(cmd, "neutro")) { NEUTRO_US = x; servo.writeMicroseconds(NEUTRO_US); imprimirConfig(); }
  else if (!strcmp(cmd, "s")) { modo = PARADO; servo.writeMicroseconds(NEUTRO_US); Serial.println(F("# parado")); }
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

void setup() {
  Serial.begin(115200);
  servo.attach(PIN_SERVO);
  servo.writeMicroseconds(NEUTRO_US);
  Serial.println(F("# pronto. Comandos: n, c, f <pulso>, p <pulso>, neutro <us>, s"));
  imprimirConfig();
}

void loop() {
  lerSerial();
  if (modo == VARRE)  passoVarredura();
  if (modo == DEGRAU) passoDegrau();
}
