# Futebol de robôs (`soccer`)

**Objetivo:** fazer gols. Cada time tem três robôs, e **um único nó controla os três**.

## Campo e regras

- campo de 1,8 × 1,2 m (eixo x no comprimento), centro em (0, 0), cercado por paredes;
- gols de 0,40 m de largura no meio de cada lado curto;
- **azul** (`hero_0`, `hero_1`, `hero_2`) ataca para **+x**; **vermelho** (`hero_3`, `hero_4`, `hero_5`) ataca para **−x**;
- a bola é uma bola de golfe laranja (raio 2,1 cm) que se move quando os robôs a empurram;
- é gol quando o centro da bola cruza a linha do gol entre as traves. Depois do gol, robôs e bola voltam às posições iniciais;
- não há tempo de jogo nem faltas. O placar acumula até o simulador ser fechado.

Posições iniciais do azul: goleiro em (−0,78; 0) e dois jogadores perto de (−0,35; ±0,25),
todos olhando para +x. O vermelho fica espelhado.

## Tópicos

| Tópico | Tipo | Uso |
|---|---|---|
| `/hero_N/odom` | `nav_msgs/Odometry` | pose de cada um dos seis robôs (N = 0 a 5) |
| `/ball/odom` | `nav_msgs/Odometry` | posição da bola em `pose.pose.position` e velocidade em `twist.twist.linear` (referencial do mundo) |
| `/hero_N/cmd_vel` | `geometry_msgs/Twist` | saída, um tópico para cada robô do seu time |
| `/game/state` | `std_msgs/String` | JSON com `blue`, `red` (placar) e as dimensões do campo |

## O que implementar (`soccer.py`)

- **TODO 1 (ROS):** assine `/hero_<i>/odom` para os seis robôs (função `self.on_odom`, passando `i`
  em `callback_args`) e `/ball/odom` (função `self.on_ball`).
- **TODO 2 (controle):** `compute_commands(poses, ball)` devolve uma lista com três pares
  `(linear_x, angular_z)`, um para cada robô de `self.ids`. `self.attack` vale +1 (azul) ou −1 (vermelho).

O parâmetro `~team` (`blue` ou `red`) é preenchido pelo launch file.

## Como rodar

```bash
./run.sh run soccer                       # seu código nos dois times
./run.sh run soccer red:=none             # só o seu time azul
./run.sh run soccer red:=soccer_v2.py     # duas versões suas, uma contra a outra
```

Argumentos: `blue:=` e `red:=` recebem o nome de um arquivo desta pasta ou `none`.

## Dicas

- comece com um atacante só: posicione o robô atrás da bola, na linha bola–gol, e depois avance;
- dê papéis fixos aos outros dois (goleiro entre a bola e o próprio gol, apoio ou marcação);
- evite que os três robôs persigam a bola ao mesmo tempo, porque eles se atrapalham;
- dois times com o mesmo código tendem a empatar: teste contra uma versão diferente.
