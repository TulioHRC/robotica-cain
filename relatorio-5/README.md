# Relatório 5: ROS e navegação


## Como reproduzir os ensaios

Antes de tudo, construa o ambiente uma vez com `./run.sh build`, como descrito no `README-kit.md`.

Cada ensaio deve começar com o simulador recém-aberto, para que o robô parta da pose inicial e o placar de metas comece em zero. Por isso, rode `./run.sh down` antes de cada ensaio. O nó encerra o ensaio sozinho depois de 300 s no `avoid` e 180 s no `goto`, contados no tempo do simulador, e mostra no terminal a mensagem `ensaio ... concluído` com o caminho do arquivo gravado. Depois disso, feche com `Ctrl-C`.

Desvio de obstáculos, configurações A e B:

```bash
./run.sh down
./run.sh run avoid
```

```bash
./run.sh down
./run.sh run avoid script:=avoid_b.py
```

Navegação até metas, conjuntos A e B:

```bash
./run.sh down
./run.sh run goto
```

```bash
./run.sh down
./run.sh run goto script:=goto_b.py
```

Cada execução grava um arquivo `avoid_A_AAAAMMDD-HHMMSS.csv` (ou `avoid_B_...`, `avoid_SV_...`, `goto_A_...`, `goto_B_...`) na pasta `logs/` do exercício. A data e a hora vêm do relógio do container, que usa UTC. Execuções interrompidas antes do fim também ficam gravadas, mas os scripts de análise as ignoram.

## Como gerar as figuras e as tabelas

Os scripts rodam fora do container, com Python 3:

```bash
python3 -m pip install -r analise/requirements.txt
python3 analise/plot_avoid.py
python3 analise/plot_goto.py
```

Por padrão, cada script usa todos os ensaios completos de cada configuração encontrados em `logs/`. As figuras mostram o ensaio mais recente, e as tabelas mostram a média e o desvio padrão quando há mais de um ensaio. Para escolher os arquivos, use `--a` e `--b`:

```bash
python3 analise/plot_avoid.py --a exercicios/avoid/logs/avoid_A_20261110-143000.csv --b exercicios/avoid/logs/avoid_B_20261110-145000.csv
```

As figuras vão para `relatorio/figs/` e as tabelas de métricas para `relatorio/dados/`. As duas pastas são criadas automaticamente na primeira execução.

## Parâmetros

`avoid`:

| Parâmetro | A | B |
|---|---|---|
| `V_LIN` (m/s) | 0,15 | 0,20 |
| `D_LENTO` (m) | 0,30 | 0,20 |
| `D_PARE` (m) | 0,08 | 0,06 |
| `K_W` (rad/s/m) | 6,0 | 6,0 |
| `W_LIM` (rad/s) | 3,0 | 3,0 |
| `W_ESC` (rad/s) | 2,5 | 2,5 |
| `D_GIRO` (m) | 0,13 | 0,09 |
| `D_LIVRE` (m) | 0,20 | 0,14 |
| `D_INF` (m) | 0,30 | 0,20 |
| `W_VAG` (rad/s) | 1,0 | 1,0 |
| `T_VAG` (iterações a 20 Hz) | 40 | 40 |

`goto`:

| Parâmetro | A | B |
|---|---|---|
| `K_ALPHA` (1/s) | 3,0 | 1,0 |
| `K_RHO` (1/s) | 1,5 | 1,5 |
| `V_LIN` (m/s) | 0,20 | 0,20 |
| `W_LIM` (rad/s) | 4,0 | 4,0 |

## Vídeos

- `avoid`: (adicionar o link)
- `goto`: (adicionar o link)