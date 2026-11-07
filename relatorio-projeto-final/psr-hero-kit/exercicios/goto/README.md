# Navegação até metas (`goto`)

**Objetivo:** levar o robô até a meta e, em seguida, à próxima meta sorteada pelo simulador, o
maior número de vezes possível. A meta conta quando o centro do robô fica a menos de **6 cm** dela.

## Arena

- quadrada, 2,0 × 2,0 m, centro em (0, 0), sem obstáculos internos;
- as metas são sorteadas dentro do quadrado de ±0,75 m e aparecem como esferas na cor do robô;
- `hero_0` começa em (−0,6; −0,6);
- o placar mostra quantas metas o robô atingiu.

## Tópicos

| Tópico | Tipo | Uso |
|---|---|---|
| `/hero_N/odom` | `nav_msgs/Odometry` | entrada: pose `(x, y, yaw)` com `pose_from_odom(msg)` |
| `/hero_N/goal` | `geometry_msgs/PointStamped` | entrada: meta atual em `msg.point.x`, `msg.point.y` |
| `/hero_N/cmd_vel` | `geometry_msgs/Twist` | saída |
| `/game/state` | `std_msgs/String` | JSON com `reached` (metas atingidas) e `last_goal_time` |

## O que implementar (`goto.py`)

- **TODO 1 (ROS):** assine `/hero_<robot>/odom` (`Odometry`, função `self.on_odom`) e
  `/hero_<robot>/goal` (`PointStamped`, função `self.on_goal`); guarde `self.pose` e `self.goal`.
- **TODO 2 (controle):** `compute_command(pose, goal)` devolve `(linear_x, angular_z)` para
  levar o robô de `pose = (x, y, yaw)` até `goal = (x, y)`.

## Como rodar

```bash
./run.sh run goto
```

Argumento opcional: `script:=outro.py`.

## Dicas

- calcule a distância e o ângulo até a meta (`math.atan2`) e o erro de orientação com `wrap_angle`;
- um controlador proporcional no erro de orientação, com a velocidade linear reduzida quando o
  erro é grande, já funciona bem;
- sature os comandos em `V_MAX` e `W_MAX` com `clamp`.
