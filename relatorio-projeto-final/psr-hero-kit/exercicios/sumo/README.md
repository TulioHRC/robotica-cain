# Sumô (`sumo`)

**Objetivo:** empurrar o adversário para fora do ringue circular sem sair dele.

## Regras

- o ringue tem raio de **0,40 m**, centro em (0, 0), e fica 6 cm acima do chão; não há parede;
- perde a rodada o robô cujo **centro** sair do ringue (ele cai). Se os dois saírem juntos, é empate;
- uma rodada sem vencedor termina empatada após **40 s**;
- `hero_0` (azul) começa em (−0,18; ~0) olhando para +x e `hero_1` (laranja) em (0,18; ~0) olhando para −x,
  com pequenas variações aleatórias de posição a cada rodada;
- depois de cada rodada os robôs voltam às posições iniciais e o jogo continua;
- os dois robôs têm a mesma tração: um empurrão frontal tende a empatar. Ângulo de ataque,
  momento certo e a própria posição no ringue fazem a diferença.

## Tópicos

| Tópico | Tipo | Uso |
|---|---|---|
| `/hero_N/odom` | `nav_msgs/Odometry` | pose do seu robô e do adversário; `twist.twist.linear.x` é a sua velocidade |
| `/hero_N/laser` | `sensor_msgs/LaserScan` | o lidar também enxerga o adversário (opcional) |
| `/hero_N/cmd_vel` | `geometry_msgs/Twist` | saída |
| `/game/state` | `std_msgs/String` | JSON com `wins`, `draws` e `round_time` |

## O que implementar (`sumo.py`)

- **TODO 1 (ROS):** assine a odometria do seu robô (`~robot`, função `self.on_me`) e a do
  adversário (`~opponent`, função `self.on_opp`).
- **TODO 2 (controle):** `compute_command(me, opp, speed, now)` devolve `(linear_x, angular_z)`;
  `me` e `opp` são `(x, y, yaw)`, `speed` é a sua velocidade para a frente e `now` é o tempo em segundos.

## Como rodar

```bash
./run.sh run sumo                        # seu código nos dois robôs
./run.sh run sumo robot1:=none           # só o hero_0; o hero_1 fica parado (bom para começar)
./run.sh run sumo robot1:=sumo_v2.py     # duas versões suas, uma contra a outra
```

Argumentos: `robot0:=` e `robot1:=` recebem o nome de um arquivo desta pasta ou `none`.

## Dicas

- comece com o adversário parado (`robot1:=none`) e faça o robô empurrá-lo para fora;
- use a distância do seu robô ao centro (`math.hypot(x, y)`) para não sair sozinho;
- empurrar na direção que leva o adversário para a borda mais próxima é mais eficaz do que empurrar para o centro dele;
- dois nós idênticos podem travar um contra o outro: experimente variações de estratégia.
