# Desvio de obstáculos (`avoid`)

**Objetivo:** manter o robô andando pela arena sem encostar no cilindro central, nem nas
paredes, usando **apenas o lidar**.

## Arena

- quadrada, 2,0 × 2,0 m, centro em (0, 0), com paredes;
- cilindro laranja de raio 0,15 m no centro;
- `hero_0` começa em (−0,7; 0) olhando para +x;
- não há placar, só o tempo decorrido. A avaliação é visual: o robô deve andar sem colidir e sem ficar preso.

## Tópicos

| Tópico | Tipo | Uso |
|---|---|---|
| `/hero_N/laser` | `sensor_msgs/LaserScan` | entrada: 8 distâncias em `msg.ranges` |
| `/hero_N/cmd_vel` | `geometry_msgs/Twist` | saída: `linear.x` e `angular.z` |

O índice dos feixes está no README principal: o feixe 4 aponta para a frente, os feixes 3 e 5
apontam 45° à direita e à esquerda, e o feixe 0 aponta para trás. Um feixe sem obstáculo mede 0,5 m.

## O que implementar (`avoid.py`)

- **TODO 1 (ROS):** em `__init__`, assine `/hero_<robot>/laser` com o tipo `LaserScan` e a
  função `self.on_scan`; em `on_scan`, guarde a mensagem em `self.scan`.
- **TODO 2 (controle):** `compute_command(ranges)` recebe a lista com as 8 distâncias e devolve
  `(linear_x, angular_z)`.

O parâmetro `~robot` (sempre 0 neste exercício) é preenchido pelo launch file.

## Como rodar

```bash
./run.sh run avoid
```

Argumento opcional: `script:=outro.py` roda outro arquivo desta pasta.

## Dicas

- comece com uma regra simples: velocidade constante e giro para o lado com mais espaço livre;
- reduza a velocidade linear quando a distância à frente diminuir, para não colidir antes de terminar o giro;
- compare a soma dos feixes da esquerda (5, 6) com a dos da direita (3, 2) para escolher o sentido do giro;
- uma estratégia reativa pura pode oscilar em cantos. Observe o comportamento e ajuste os ganhos.
