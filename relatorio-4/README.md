# Relatório 4 — Encoder de roda e controle PID

Material de apoio do relatório 4, copiado de `arduino-wheel-encoder/` (que continua sendo o projeto PlatformIO de origem).
O texto LaTeX do relatório está em `../relatorio4/`.

Parâmetros da roda: D = 4 cm, N = 245 ticks/volta, k = π·D/N ≈ 0,51 mm/tick.

## Estrutura
- `codigo/calibracao/`: `calculate_n*.cpp` (contagem de ticks por volta) e `calculate_v.cpp` (velocidade a partir do encoder).
- `codigo/malha_aberta/`: `malha_aberta.cpp` (neutro, curva pulso×velocidade, filtros) e `registrar_malha_aberta.py` (grava CSV/PNG).
- `codigo/pid/`: `roda_pid.cpp` (PID de velocidade; idêntico a `arduino-wheel-encoder/src/main.cpp`), `registrar_roda_pid.py` e `graph.py` (gráfico ao vivo).
- `codigo/platformio.ini`: configuração da Mega 2560 (libs `Servo`, `Encoder`).
- `registros/`: CSV + PNG de todos os ensaios, prefixados por tipo:

| Prefixo | Ensaio |
|---|---|
| `neutro_` | busca do pulso neutro |
| `curva_` | curva pulso × velocidade |
| `filtros_` | degrau em malha aberta, comparando filtros |
| `manual_` | sintonia do PID (degraus `v 100`) |
| `patamares_` | ensaio 1: cinco patamares crescentes |
| `inversao_` | ensaio 2: inversão de sentido |

Datas: 29/10/2026 (malha aberta e primeiras sintonias) e 03/11/2026 (sintonia final e ensaios 1 e 2).
