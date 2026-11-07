#!/usr/bin/env bash
# Entry point of the HeRo simulation kit. Run ./run.sh help.
set -euo pipefail
cd "$(dirname "$0")"

TORCH_VERSION=2.14.1
GENESIS_VERSION=1.4.3
SIM_PORT=11312
NET=psrkit

usage() {
  cat <<'USAGE'
Kit de simulação do HeRo (Genesis + ROS 1 Noetic)

  ./run.sh build [cpu|gpu]           prepara o ambiente (só na primeira vez; gpu = NVIDIA no Linux)
  ./run.sh run <cenário> [-n N] [args do roslaunch]
                                     abre o simulador (se ainda não estiver aberto) e roda o seu código
  ./run.sh sim <cenário> [-n N]      só abre o simulador
  ./run.sh shell                     terminal no container ROS em execução (rostopic, rosnode, ...)
  ./run.sh logs                      mensagens do simulador
  ./run.sh down                      fecha tudo

Cenários: avoid (1 robô), goto (1), sumo (2), soccer (6), ctf (2 ou 4).
Opções:   -n N  número de robôs     --cpu / --gpu  escolhe a imagem do simulador

Exemplos:
  ./run.sh build
  ./run.sh run avoid
  ./run.sh run goto
  ./run.sh run sumo robot1:=none          só o hero_0 com o seu código
  ./run.sh run soccer red:=soccer_v2.py   seu time azul contra outra versão
USAGE
}

die() { echo "erro: $*" >&2; exit 1; }
info() { echo "[psr] $*"; }

OS=$(uname -s)
is_mac() { [ "$OS" = Darwin ]; }
is_wsl() { grep -qi microsoft /proc/version 2>/dev/null; }

default_robots() {
  case "$1" in
    avoid|goto) echo 1 ;;
    sumo) echo 2 ;;
    ctf) echo 4 ;;
    soccer) echo 6 ;;
    *) die "cenário desconhecido '$1' (avoid, goto, sumo, soccer, ctf)" ;;
  esac
}

check_robots() {  # scenario n
  case "$1:$2" in
    avoid:1|goto:1|sumo:2|soccer:6|ctf:2|ctf:4) ;;
    *) die "o cenário '$1' não aceita $2 robô(s)" ;;
  esac
}

need_docker() {
  command -v docker >/dev/null || die "Docker não encontrado (veja o README.md)."
  docker info >/dev/null 2>&1 || die "o Docker está instalado mas não está rodando (abra o Docker Desktop ou inicie o serviço)."
}

flavor() {  # cpu | gpu, from the option or from the last build
  if [ -n "${FLAVOR:-}" ]; then echo "$FLAVOR"
  elif [ -f .flavor ]; then cat .flavor
  else echo cpu
  fi
}

# --- build -----------------------------------------------------------------------

pip_install() {  # pip install, hiding the expected "genesis-world requires X" warnings (the slim
  # environment leaves those packages out on purpose) but showing everything on failure
  local log
  log=$(mktemp)
  if ! .venv/bin/pip install -q "$@" >"$log" 2>&1; then cat "$log"; rm -f "$log"; return 1; fi
  grep -vE "requires .*which is not installed|dependency resolver|dependency conflicts" "$log" || true
  rm -f "$log"
}

build_venv() {  # macOS: the simulator runs natively (Docker Desktop has no OpenGL for windows)
  local py
  py=$(command -v python3.12 || command -v python3.11 || command -v python3.13 || command -v python3.10 || true)
  [ -n "$py" ] || die "o simulador precisa de Python 3.10 a 3.13 (instale com: brew install python@3.12)"
  if [ ! -x .venv/bin/python ]; then
    info "criando .venv com $py"
    "$py" -m venv .venv
  fi
  pip_install --upgrade pip
  pip_install "torch==$TORCH_VERSION"
  pip_install --no-deps "genesis-world==$GENESIS_VERSION"
  pip_install -r docker/sim-requirements.txt
  local site
  site=$(.venv/bin/python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
  cp docker/psr_slim_stubs.py "$site/"
  echo "import psr_slim_stubs" > "$site/psr_slim_stubs.pth"
}

cmd_build() {
  need_docker
  local f=${1:-cpu}
  case "$f" in cpu|gpu) ;; *) die "use: ./run.sh build [cpu|gpu]" ;; esac
  info "imagem ROS (psr-kit-ros)"
  docker build -t psr-kit-ros -f docker/ros.Dockerfile .
  if is_mac; then
    info "simulador nativo no macOS (.venv)"
    build_venv
  else
    info "imagem do simulador (psr-kit-sim:$f)"
    docker build -t "psr-kit-sim:$f" --build-arg FLAVOR="$f" -f docker/sim.Dockerfile .
  fi
  echo "$f" > .flavor
  info "pronto. Próximo passo: ./run.sh run avoid"
}

# --- simulator -------------------------------------------------------------------

sim_running() {  # prints "scenario robots" of the running simulator, if any
  if is_mac; then
    [ -f .sim.pid ] && kill -0 "$(cat .sim.pid)" 2>/dev/null && cat .sim.state 2>/dev/null || true
  else
    docker inspect -f '{{.State.Running}} {{index .Config.Labels "psr.scenario"}} {{index .Config.Labels "psr.robots"}}' psrkit-sim 2>/dev/null \
      | awk '$1 == "true" {print $2, $3}' || true
  fi
}

sim_stop() {
  if is_mac; then
    if [ -f .sim.pid ]; then kill "$(cat .sim.pid)" 2>/dev/null || true; fi
    rm -f .sim.pid .sim.state
  else
    docker rm -f psrkit-sim >/dev/null 2>&1 || true
  fi
}

x11_socket_dir() {
  if is_wsl && docker info --format '{{.OperatingSystem}}' 2>/dev/null | grep -qi "docker desktop"; then
    echo /run/desktop/mnt/host/wslg/.X11-unix  # WSLg as seen by the Docker Desktop VM
  else
    echo /tmp/.X11-unix
  fi
}

sim_start_docker() {  # scenario n
  local f backend args
  f=$(flavor); backend=cpu
  docker image inspect "psr-kit-sim:$f" >/dev/null 2>&1 || die "imagem psr-kit-sim:$f não existe: rode ./run.sh build $f"
  [ -n "${DISPLAY:-}" ] || die "DISPLAY não definido: rode no terminal da sessão gráfica (no Windows, dentro do WSL2)"
  command -v xhost >/dev/null && xhost +local: >/dev/null 2>&1 || true
  docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET" >/dev/null
  args=(-d --name psrkit-sim --network "$NET" --label "psr.scenario=$1" --label "psr.robots=$2"
        -e DISPLAY="$DISPLAY" -v "$(x11_socket_dir):/tmp/.X11-unix"
        -v "psrkit-cache-$f:/root/.cache")  # compiled kernels: the next start is much faster
  if [ -n "${XAUTHORITY:-}" ] && [ -f "$XAUTHORITY" ]; then
    args+=(-e XAUTHORITY=/tmp/.Xauthority -v "$XAUTHORITY:/tmp/.Xauthority:ro")
  fi
  [ -e /dev/dri ] && args+=(--device /dev/dri)  # Intel/AMD graphics
  if [ "$f" = gpu ]; then
    backend=gpu
    args+=(--gpus all -e NVIDIA_DRIVER_CAPABILITIES=all)
  fi
  docker run "${args[@]}" "psr-kit-sim:$f" \
    python -m psr_sim --viewer --scenario "$1" --robots "$2" --backend "$backend" >/dev/null
}

sim_start_mac() {  # scenario n
  [ -x .venv/bin/python ] || die "ambiente não preparado: rode ./run.sh build"
  local backend=cpu
  [ "$(flavor)" = gpu ] && backend=gpu  # Metal on Apple silicon
  (cd sim && exec nohup ../.venv/bin/python -m psr_sim --viewer --scenario "$1" --robots "$2" \
     --backend "$backend" --tcp-port "$SIM_PORT" >../.sim.log 2>&1) &
  echo $! > .sim.pid
  echo "$1 $2" > .sim.state
}

sim_logs() {
  if is_mac; then cat .sim.log 2>/dev/null; else docker logs psrkit-sim 2>&1; fi
}

sim_ensure() {  # scenario n: start (or restart) the simulator when needed
  local want="$1 $2" have
  have=$(sim_running)
  if [ "$have" = "$want" ]; then return 0; fi
  [ -n "$have" ] && info "fechando o simulador atual ($have)"
  sim_stop
  info "abrindo o simulador: $1 com $2 robô(s) (a primeira abertura pode levar 1-2 min)"
  if is_mac; then sim_start_mac "$1" "$2"; else sim_start_docker "$1" "$2"; fi
  printf '[psr] aguardando o simulador'
  for _ in $(seq 1 180); do
    if sim_logs | grep -q "bridge on tcp"; then echo " ok"; return 0; fi
    if [ -z "$(sim_running)" ]; then echo; sim_logs | tail -n 25; die "o simulador fechou (mensagens acima)"; fi
    printf '.'; sleep 1
  done
  echo; sim_logs | tail -n 25; die "o simulador não respondeu"
}

# --- ROS -------------------------------------------------------------------------

ros_run() {  # command...: a fresh ROS container with the exercises mounted
  docker image inspect psr-kit-ros >/dev/null 2>&1 || die "imagem psr-kit-ros não existe: rode ./run.sh build"
  docker rm -f psrkit-ros >/dev/null 2>&1 || true
  local args=(--rm --name psrkit-ros -v "$PWD/exercicios:/ws/psr_exercicios")
  [ -t 0 ] && args+=(-it)
  if is_mac; then
    args+=(-e PSR_SIM_HOST=host.docker.internal -e PSR_SIM_PORT="$SIM_PORT")
  else
    args+=(--network "$NET" -e PSR_SIM_HOST=psrkit-sim -e PSR_SIM_PORT="$SIM_PORT")
  fi
  docker run "${args[@]}" psr-kit-ros "$@"
}

parse_scenario() {  # sets SCENARIO, N, REST
  [ $# -ge 1 ] || die "falta o cenário (avoid, goto, sumo, soccer, ctf)"
  SCENARIO=$1; shift
  N=$(default_robots "$SCENARIO"); REST=()
  while [ $# -gt 0 ]; do
    case "$1" in
      -n|--robots) [ $# -ge 2 ] || die "-n precisa de um número"; N=$2; shift 2 ;;
      --cpu) FLAVOR=cpu; shift ;;
      --gpu) FLAVOR=gpu; shift ;;
      *) REST+=("$1"); shift ;;
    esac
  done
  check_robots "$SCENARIO" "$N"
}

cmd_run() {
  need_docker
  parse_scenario "$@"
  sim_ensure "$SCENARIO" "$N"
  local extra=()
  [ "$SCENARIO" = ctf ] && extra=("robots:=$N")
  info "rodando exercicios/$SCENARIO (Ctrl-C para parar; o simulador continua aberto)"
  ros_run roslaunch psr_exercicios "$SCENARIO.launch" ${extra[@]+"${extra[@]}"} ${REST[@]+"${REST[@]}"}
}

cmd=${1:-help}; [ $# -gt 0 ] && shift || true
case "$cmd" in
  help|-h|--help) usage ;;
  build) cmd_build "$@" ;;
  run) cmd_run "$@" ;;
  sim)
    need_docker; parse_scenario "$@"
    sim_ensure "$SCENARIO" "$N"
    info "simulador aberto. Agora: ./run.sh run $SCENARIO"
    ;;
  shell)
    need_docker
    docker inspect -f '{{.State.Running}}' psrkit-ros 2>/dev/null | grep -q true \
      || die "nenhum container ROS rodando: inicie um cenário com ./run.sh run <cenário> em outro terminal"
    docker exec -it psrkit-ros /ros-entrypoint.sh bash
    ;;
  logs) sim_logs ;;
  down)
    need_docker
    docker rm -f psrkit-ros >/dev/null 2>&1 || true
    sim_stop
    info "tudo fechado"
    ;;
  *) usage; exit 1 ;;
esac
