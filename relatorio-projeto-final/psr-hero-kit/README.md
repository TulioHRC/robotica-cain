# Kit de simulação do HeRo — Projeto de Sistemas Robóticos (DCC/UFMG)

Ambiente para os exercícios de ROS e navegação com o robô
[HeRo](https://github.com/verlab/hero_common). A física e a janela 3D usam o simulador
[Genesis](https://genesis-world.readthedocs.io/). O seu código roda em **ROS 1 Noetic**
(Python) e usa os mesmos tópicos do robô real.

```
 ┌──────────── simulador ────────────┐        ┌─────────────── ROS ───────────────┐
 │ Genesis: física + janela 3D       │  TCP   │ hero_bridge  ◄──►  seu código     │
 │ cenário e juiz (placar)           │◄──────►│ /hero_N/odom, /hero_N/laser,      │
 └───────────────────────────────────┘        │ /hero_N/cmd_vel, ...              │
                                              └───────────────────────────────────┘
```

## Exercícios

| Pasta | Robôs | Tarefa |
|---|---|---|
| [`exercicios/avoid`](exercicios/avoid/README.md) | 1 | andar pela arena sem colidir, usando apenas o lidar |
| [`exercicios/goto`](exercicios/goto/README.md) | 1 | navegar de meta em meta (*goal to goal*) com a odometria |
| [`exercicios/sumo`](exercicios/sumo/README.md) | 2 | empurrar o adversário para fora do ringue |
| [`exercicios/soccer`](exercicios/soccer/README.md) | 6 | futebol 3×3: um nó controla os três robôs do time |
| [`exercicios/ctf`](exercicios/ctf/README.md) | 4 ou 2 | rouba-bandeira 2×2, com atacante e defensor |

Cada pasta tem um arquivo Python com a estrutura pronta (publicador, laço de controle) e
dois pontos a completar, marcados no código:

- **TODO 1 (ROS):** criar os *subscribers* dos tópicos e guardar as mensagens;
- **TODO 2 (controle):** transformar os dados dos sensores em um comando de velocidade.

## Requisitos

| Sistema | O que instalar |
|---|---|
| **Linux** (Ubuntu 20.04 ou mais novo) | [Docker Engine](https://docs.docker.com/engine/install/). Use o Docker Engine, não o Docker Desktop, porque a janela do simulador usa o servidor X da máquina. |
| **Windows 10/11** | WSL2 com Ubuntu (`wsl --install` no PowerShell como administrador) e Docker Desktop com a integração WSL ativada, ou o Docker Engine instalado dentro do Ubuntu do WSL. Rode todos os comandos **no terminal do Ubuntu (WSL2)**, com o kit dentro do sistema de arquivos do Linux (por exemplo, em `~/psr-hero-kit`, e não em `/mnt/c/...`). A janela aparece pelo WSLg. |
| **macOS** (Intel ou Apple silicon) | [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/) e Python 3.12 (`brew install python@3.12`). No macOS o simulador roda direto na máquina, em um ambiente Python próprio (`.venv`), porque o Docker do Mac não abre janelas com OpenGL. O ROS roda no Docker do mesmo jeito. |

Download e espaço em disco das imagens (medidos em um PC x86-64):

| Parte | Download | Em disco |
|---|---|---|
| imagem ROS (`psr-kit-ros`) | ~270 MB | ~0,9 GB |
| imagem do simulador, CPU (`psr-kit-sim:cpu`) | ~480 MB | ~1,6 GB |
| imagem do simulador, GPU (`psr-kit-sim:gpu`) | ~2,9 GB | ~5,3 GB |

Só é preciso construir uma das imagens do simulador (CPU ou GPU).

A memória RAM mínima recomendada é de 8 GB. No Windows, o WSL2 usa parte dela.

## Instalação (uma vez)

Descompacte o kit, abra um terminal na pasta e escolha a versão do simulador:

```bash
cd psr-hero-kit
./run.sh build          # versão CPU: funciona em qualquer máquina (recomendada)
./run.sh build gpu      # versão GPU: só Linux/WSL2 com placa NVIDIA (veja abaixo)
```

O comando baixa as dependências e monta as imagens. A primeira vez leva de 5 a 15
minutos, conforme a internet. Os dois *builds* podem coexistir: `./run.sh run <cenário> --cpu`
ou `--gpu` escolhe qual usar (o padrão é o último construído).

**CPU ou GPU?** Os cenários têm poucos corpos e rodam bem na CPU. A versão GPU usa CUDA na
física e o OpenGL da placa NVIDIA na janela. Ela exige o driver NVIDIA (versão 525 ou mais
nova) e o [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
Sem GPU NVIDIA, use a versão CPU. No Linux com vídeo Intel ou AMD, a versão CPU pode usar a
placa para desenhar a janela (via `/dev/dri`); sem ela, o desenho é feito por software.

## Uso

```bash
./run.sh run avoid
```

O comando abre a janela do simulador (a primeira abertura de cada cenário leva cerca de
30 s) e roda o seu código de `exercicios/avoid/avoid.py`. As mensagens dos seus nós
aparecem no terminal.

O ciclo de trabalho é:

1. edite o arquivo do exercício no seu editor, na sua máquina (a pasta `exercicios/` é
   montada dentro do container, então não há nada para copiar nem reconstruir);
2. rode `./run.sh run <cenário>`;
3. pare com `Ctrl-C`, ajuste o código e rode de novo. **O simulador continua aberto**
   entre uma execução e outra, então o reinício é imediato.

Comandos:

| Comando | Para quê |
|---|---|
| `./run.sh run <cenário> [-n N] [args]` | abre o simulador (se preciso) e roda o seu código |
| `./run.sh sim <cenário> [-n N]` | só abre o simulador |
| `./run.sh shell` | abre um terminal no container ROS em execução (`rostopic`, `rosnode`, ...) |
| `./run.sh logs` | mostra as mensagens do simulador |
| `./run.sh down` | fecha tudo |

Fechar a janela do simulador encerra o simulador. O próximo `./run.sh run` abre outro.
Rodar outro cenário (ou outro número de robôs) troca o simulador automaticamente.

Exemplos:

```bash
./run.sh run goto script:=goto_v2.py     # outra versão do goto (goto/goto_v2.py)
./run.sh run sumo robot1:=none           # só o hero_0 é controlado pelo seu código
./run.sh run soccer red:=soccer_v2.py    # seu time azul contra outra versão (soccer/soccer_v2.py)
./run.sh run ctf -n 2                    # rouba-bandeira 1×1
```

Para testar uma versão nova sem perder a anterior, copie o arquivo dentro da mesma pasta
(por exemplo `cp exercicios/sumo/sumo.py exercicios/sumo/sumo_v2.py`) e passe o nome
no argumento do lado correspondente. Os nomes dos argumentos de cada cenário estão no
README da pasta.

### Inspecionar os tópicos

Com um cenário rodando, abra outro terminal:

```bash
./run.sh shell
rostopic list
rostopic echo /hero_0/laser
rostopic hz /hero_0/odom
rosmsg show sensor_msgs/LaserScan
```

## Interface com o robô

Os tópicos seguem o HeRo real. `N` é o número do robô (`hero_0`, `hero_1`, ...).

| Tópico | Tipo | Conteúdo |
|---|---|---|
| `/hero_N/cmd_vel` | `geometry_msgs/Twist` | **o que você publica**: `linear.x` (m/s) e `angular.z` (rad/s) |
| `/hero_N/odom` | `nav_msgs/Odometry` | pose (x, y, orientação) no referencial `world` e velocidades |
| `/hero_N/laser` | `sensor_msgs/LaserScan` | lidar de 8 feixes, alcance de 0,037 a 0,5 m |
| `/hero_N/goal` | `geometry_msgs/PointStamped` | meta atual (só no `goto`) |
| `/ball/odom` | `nav_msgs/Odometry` | posição e velocidade da bola (só no `soccer`) |
| `/flag/blue`, `/flag/red` | `geometry_msgs/PointStamped` | posição das bandeiras (só no `ctf`) |
| `/hero_N/has_flag` | `std_msgs/Bool` | o robô N carrega a bandeira inimiga (só no `ctf`) |
| `/game/state` | `std_msgs/String` | JSON com placar e tempo da rodada |

Os tópicos são publicados a 25 Hz. Limites do robô: `|linear.x| ≤ 0,2 m/s` e
`|angular.z| ≤ 4 rad/s` (valores acima são saturados). Sem receber comando por 0,5 s,
o robô para, como no firmware real.

**Lidar.** O feixe `k` (de 0 a 7) aponta para o ângulo `-π + k·π/4` em relação à frente do
robô, no sentido anti-horário:

```
                frente
                   4
            5      ▲      3
  esquerda  6    (robô)   2  direita
            7             1
                   0
                 trás
```

Um feixe que não encontra nada mede 0,5 m. As distâncias são medidas a partir do centro do
robô, então um robô encostado na parede lê cerca de 0,037 m. O lidar enxerga paredes,
obstáculos, outros robôs e a bola.

**Funções auxiliares** (`from psr_hero.utils import ...`):

| Nome | O que faz |
|---|---|
| `V_MAX`, `W_MAX` | limites de velocidade (0,2 m/s e 4 rad/s) |
| `pose_from_odom(msg)` | devolve `(x, y, yaw)` de uma mensagem `Odometry` |
| `wrap_angle(a)` | normaliza um ângulo para o intervalo `[-π, π)` |
| `clamp(x, lo, hi)` | limita `x` ao intervalo `[lo, hi]` |
| `beam_angle(k)` | ângulo (rad) do feixe `k` do lidar |
| `yaw_from_quaternion(q)` | orientação em torno de z de um `Quaternion` |

Para usar outras bibliotecas Python, o container ROS já tem `numpy`.

## Problemas comuns

| Sintoma | O que fazer |
|---|---|
| `DISPLAY não definido` | rode o comando no terminal da sessão gráfica. No Windows, no terminal do Ubuntu (WSL2). Por SSH a janela não abre. |
| `cannot open display` / a janela não aparece (Linux) | rode `xhost +local:` e tente de novo. Confirme que é o Docker Engine, não o Docker Desktop. |
| o simulador fecha logo ao abrir | `./run.sh logs` mostra o erro. Na versão GPU, teste o toolkit com `docker run --rm --gpus all ubuntu nvidia-smi`. |
| a janela fica lenta | a renderização por software (sem placa de vídeo acessível) é mais pesada. Feche outros programas, ou use a versão GPU se tiver placa NVIDIA. |
| `waiting for odometry (TODO 1)` no terminal | os *subscribers* do TODO 1 ainda não estão feitos ou usam o nome errado do tópico. |
| o robô não se mexe | confira se `compute_command` devolve valores diferentes de zero e se o tópico é `/hero_<robot>/cmd_vel`. |
| `Permission denied` ao rodar `./run.sh` | `chmod +x run.sh` (zip extraído no Windows perde a permissão). |

## Créditos e licença

Código sob a licença MIT (`LICENSE`). Os modelos 3D do HeRo vêm do
[hero_common](https://github.com/verlab/hero_common) (VeRLab/UFMG, CC BY-NC-SA 4.0); veja `NOTICE.md`.
