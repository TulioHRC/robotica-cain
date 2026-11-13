# Projeto final: sumô, rouba-bandeira e futebol

Projeto de Sistemas Robóticos, DCC/UFMG, 2º semestre de 2026.

Equipe: Ari Filho, Caio Costa, Cleiton Neves e Túlio Henrique.

Este repositório é o kit de simulação `psr-hero-kit` da disciplina acrescido das estratégias da equipe para os três jogos do projeto final. A instalação do kit está descrita em [`README-kit.md`](README-kit.md). Os arquivos do Relatório 5 estão descritos em [`README-tp5.md`](README-tp5.md).

## Arquivos

| Caminho                          | Conteúdo                                                           | Responsável |
| -------------------------------- | ------------------------------------------------------------------ | ----------- |
| `exercicios/sumo/sumo.py`        | versão final do sumô (arquivo de competição): estratégia órbita    | Ari         |
| `exercicios/sumo/sumo_v1.py`     | versão anterior, usada nas comparações: mira para a borda          | Ari         |
| `exercicios/ctf/ctf.py`          | versão final do rouba-bandeira (arquivo de competição)             | Caio        |
| `exercicios/ctf/ctf_v1.py`       | versão anterior                                                    | Caio        |
| `exercicios/soccer/soccer.py`    | versão final do futebol (arquivo de competição)                    | Túlio       |
| `exercicios/soccer/soccer_v1.py` | versão anterior                                                    | Túlio       |
| `exercicios/registro/placar.py`  | nó que grava o placar de uma partida em CSV (só para testes)       | Cleiton     |
| `exercicios/registro/logs/`      | registros das partidas                                             | todos       |
| `partidas.sh`                    | roda partidas completas, reiniciando o simulador antes de cada uma | Cleiton     |
| `analise/tabelas.py`             | gera as tabelas de resultados do relatório a partir dos registros  | Cleiton     |
| `analise/verificar_regras.py`    | confere as regras do enunciado nos três arquivos de competição     | Cleiton     |
| `videos/`                        | vídeos dos três jogos                                              | todos       |

Os arquivos de competição são `sumo.py`, `ctf.py` e `soccer.py`. Cada um é autocontido e funciona dos dois lados. O registrador e os scripts de análise não são usados nas partidas da competição.

## Vídeos

- Sumô: [`videos/sumo_final.mp4`](videos/sumo_final.mp4)
- Rouba-bandeira: (adicionar o link)
- Futebol: (adicionar o link)

## Como jogar

Construa o ambiente uma vez com `./run.sh build`. Depois, cada jogo roda com o comando do kit:

```bash
./run.sh run sumo robot1:=none
./run.sh run ctf red:=none
./run.sh run soccer red:=soccer_v1.py
```

No sumô, os argumentos são `robot0:=` e `robot1:=`. No rouba-bandeira e no futebol, são `blue:=` e `red:=`. Cada um recebe o nome de um arquivo da pasta do jogo ou `none`, para deixar o lado parado.

## Como reproduzir as partidas de avaliação

O script `partidas.sh` faz cada partida do começo ao fim. Ele fecha o simulador, abre o jogo com os dois lados pedidos, grava o placar com `placar.py` até o fim da partida e fecha tudo de novo. No rouba-bandeira e no futebol, a partida dura 300 s de tempo simulado. No sumô, a sessão termina depois de 20 rodadas.

Uma partida, ou várias seguidas:

```bash
./partidas.sh soccer soccer.py none
./partidas.sh ctf ctf_v1.py ctf.py 3
```

Todas as partidas de avaliação de um jogo, com a versão final contra o adversário parado e contra a versão anterior, dos dois lados:

```bash
./partidas.sh avaliacao sumo
./partidas.sh avaliacao ctf
./partidas.sh avaliacao soccer
```

A avaliação do sumô tem 4 sessões de 20 rodadas. As do rouba-bandeira e do futebol têm 12 partidas cada, 3 por condição, e levam pouco mais de uma hora.

Cada partida grava um arquivo `<jogo>_<time0>_x_<time1>_<data>.csv` em `exercicios/registro/logs/`, por exemplo `soccer_soccer_v1_x_soccer_20261118-201500.csv`. O nome identifica os dois lados, e é por ele que o script de tabelas sabe qual é a condição. A data e a hora vêm do relógio do container, que usa UTC.

Também é possível rodar o registrador à mão, com o jogo já aberto em outro terminal:

```bash
./run.sh shell
rosrun psr_exercicios placar.py _jogo:=soccer _time0:=soccer.py _time1:=none
```

Os parâmetros `_duracao:=` (em segundos) e `_rodadas:=` mudam o fim da partida. No `partidas.sh`, as variáveis de ambiente `DURACAO` e `RODADAS` fazem o mesmo.

## Como gerar as tabelas do relatório

Fora do container, com Python 3 e sem bibliotecas extras:

```bash
python3 analise/tabelas.py
```

O script lê todos os registros, ignora as partidas incompletas e grava `relatorio_final/dados/tab_sumo.tex`, `tab_ctf.tex` e `tab_soccer.tex`, criando a pasta se ela não existir. Essas tabelas usam as macros da documentação em LaTeX da equipe e entram nela automaticamente. Os resultados são sempre do ponto de vista da versão final: `sumo.py`, `ctf.py` ou `soccer.py`. O adversário `none` aparece como parado, e `<jogo>_v1.py` aparece como anterior.

## Como conferir as regras do código

```bash
python3 analise/verificar_regras.py
```

Para cada arquivo de competição, o script confere se ele existe, se só importa Python padrão, `numpy`, `rospy`, as mensagens do container e `psr_hero.utils`, se não depende de outros arquivos da equipe, se só publica em `cmd_vel`, se não lê o teclado e se lê os parâmetros de lado. A verificação é estática, então ainda é preciso testar cada arquivo dos dois lados. Rode o script antes de cada commit dos arquivos de competição.
