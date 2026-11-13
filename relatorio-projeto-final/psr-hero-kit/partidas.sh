#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

uso() {
  echo "uso: ./partidas.sh <jogo> <time0> <time1> [quantidade]"
  echo "     ./partidas.sh avaliacao <jogo>"
  echo "jogo: sumo, ctf ou soccer. time0 e time1: arquivo da pasta do jogo ou none."
  exit 1
}

argumentos() {
  if [ "$1" = "sumo" ]; then echo "robot0 robot1"; else echo "blue red"; fi
}

partida() {
  local jogo="$1" t0="$2" t1="$3"
  local a0 a1
  read -r a0 a1 <<< "$(argumentos "$jogo")"
  local saida="${TMPDIR:-/tmp}/partida_${jogo}.txt"
  echo ">> $jogo: $t0 x $t1"
  ./run.sh down > /dev/null
  ./run.sh run "$jogo" "$a0:=$t0" "$a1:=$t1" < /dev/null > "$saida" 2>&1 &
  local pid=$!
  until docker inspect -f '{{.State.Running}}' psrkit-ros 2>/dev/null | grep -q true; do
    kill -0 "$pid" 2>/dev/null || { echo "o cenário não abriu, veja $saida"; exit 1; }
    sleep 1
  done
  # a imagem do kit não tem o rosbash (rosrun): chama o script direto com python3
  docker exec psrkit-ros /ros-entrypoint.sh python3 /ws/psr_exercicios/registro/placar.py \
    "_jogo:=$jogo" "_time0:=$t0" "_time1:=$t1" "_duracao:=${DURACAO:-300}" "_rodadas:=${RODADAS:-20}"
  ./run.sh down > /dev/null
  wait "$pid" 2>/dev/null || true
}

avaliacao() {
  local jogo="$1" n=3
  if [ "$jogo" = "sumo" ]; then n=1; fi
  for adv in none "${jogo}_v1.py"; do
    for k in $(seq "$n"); do
      partida "$jogo" "$jogo.py" "$adv"
      partida "$jogo" "$adv" "$jogo.py"
    done
  done
}

[ $# -ge 2 ] || uso
if [ "$1" = "avaliacao" ]; then
  avaliacao "$2"
else
  [ $# -ge 3 ] || uso
  for k in $(seq "${4:-1}"); do partida "$1" "$2" "$3"; done
fi
echo "registros em exercicios/registro/logs/"
