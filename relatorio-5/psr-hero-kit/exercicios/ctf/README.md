# Rouba-bandeira (`ctf`)

**Objetivo:** pegar a bandeira do adversário e levá-la até a sua base, sem ser capturado no
campo inimigo. Com quatro robôs, cada time tem um **atacante** e um **defensor**, e o mesmo
arquivo controla os dois (o parâmetro `~role` diz qual papel o nó tem).

## Arena e times

- arena quadrada de 1,6 × 1,6 m, dividida ao meio em x = 0;
- **azul**: base e bandeira em (−0,62; 0), robôs `hero_0` (atacante) e `hero_1` (defensor);
- **vermelho**: base e bandeira em (+0,62; 0), robôs `hero_2` (atacante) e `hero_3` (defensor);
- com dois robôs (`-n 2`), `hero_0` é o azul e `hero_1` é o vermelho, ambos atacantes.

## Regras

- encostar na bandeira inimiga (menos de 7 cm) faz o robô carregá-la, e ela passa a segui-lo;
- levar a bandeira até o círculo da própria base (raio de 0,14 m em torno da sua bandeira) vale **um ponto**;
- **na sua metade**, encostar em um adversário (menos de 10 cm) o **segura parado por 4 s**: os comandos dele
  são ignorados, e o jogo continua para os demais. Se ele carregava a sua bandeira, ela volta para a base;
- um robô segurado não pode segurar outros e, depois de solto, fica imune por 1,5 s;
- na metade do adversário, quem pode ser segurado é você;
- 90 s sem ponto é empate, e todos voltam às posições iniciais.

## Tópicos

| Tópico | Tipo | Uso |
|---|---|---|
| `/hero_N/odom` | `nav_msgs/Odometry` | pose de cada robô |
| `/flag/blue`, `/flag/red` | `geometry_msgs/PointStamped` | posição atual de cada bandeira |
| `/hero_N/has_flag` | `std_msgs/Bool` | o robô N está carregando a bandeira inimiga |
| `/hero_N/laser` | `sensor_msgs/LaserScan` | o lidar também enxerga os outros robôs (opcional) |
| `/hero_N/cmd_vel` | `geometry_msgs/Twist` | saída |
| `/game/state` | `std_msgs/String` | JSON com `score`, `held`, `carrying` e `round_time` |

Parâmetros preenchidos pelo launch file: `~robot` (o seu id), `~team` (`blue` ou `red`),
`~role` (`attacker` ou `defender`) e `~opponents` (lista com os ids dos adversários).

## O que implementar (`ctf.py`)

- **TODO 1 (ROS):** assine a odometria do seu robô (`self.on_me`) e a de cada adversário
  (`self.on_opp`, com o id em `callback_args`), a bandeira inimiga (`self.on_enemy_flag`), a sua
  bandeira (`self.on_own_flag`) e `/hero_<robot>/has_flag` (`self.on_has_flag`).
- **TODO 2 (controle):** `compute_command(me, opponents, enemy_flag, own_flag, carrying)` devolve
  `(linear_x, angular_z)`. Use `self.role` para separar o comportamento do atacante e o do defensor.

## Como rodar

```bash
./run.sh run ctf                        # 2×2, seu código nos dois times
./run.sh run ctf red:=none              # só o seu time azul (o vermelho fica parado)
./run.sh run ctf red:=ctf_v2.py         # duas versões suas, uma contra a outra
./run.sh run ctf -n 2                   # 1×1
```

Argumentos: `blue:=` e `red:=` recebem o nome de um arquivo desta pasta ou `none`.

## Dicas

- comece pelo atacante contra um time parado (`red:=none`): ir até a bandeira e voltar para a base;
- o defensor pode ficar entre a própria bandeira e o atacante adversário, avançando só quando ele cruza x = 0;
- quando `own_flag` está longe da sua base, um adversário está com a sua bandeira: persiga-o na sua metade;
- no campo inimigo, o atacante deve desviar do defensor adversário (a odometria dele está em `opponents`).
