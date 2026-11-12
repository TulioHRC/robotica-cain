#!/usr/bin/env bash
# Roda as 12 partidas do rouba-bandeira do relatório e grava os registros.
#
#   4 confrontos x 3 partidas de 5 min:
#     final (azul)     x parado (vermelho)
#     parado (azul)    x final (vermelho)
#     final (azul)     x v1 (vermelho)
#     v1 (azul)        x final (vermelho)
#
# Uso, na raiz do kit (onde fica o run.sh):
#   ./exercicios/ctf/rodar_partidas.sh
#   MIN=1 REPS=1 ./exercicios/ctf/rodar_partidas.sh      # teste rápido
#   SO=v1 ./exercicios/ctf/rodar_partidas.sh             # só os confrontos com "v1" no nome
#   SO=v1 PASTA=20261111-1846 ./exercicios/ctf/rodar_partidas.sh   # completa uma rodada anterior
#
# Variáveis: MIN (minutos de jogo, 5), REPS (partidas por confronto, 3), FINAL (ctf.py),
# ANTERIOR (ctf_v1.py), SO (filtro pelo nome do confronto), REINICIAR (1 = reabre o
# simulador antes de cada partida, para o placar e as posições começarem do zero),
# PASTA (nome de uma pasta de partidas já existente, para acrescentar a ela).
#
# Saída: exercicios/ctf/partidas/<data-hora>/ com resumo.csv (uma linha por partida) e,
# para cada partida, <nome>_amostras.csv, <nome>_eventos.csv, <nome>.json e <nome>_launch.log.
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 1
[ -x ./run.sh ] || { echo "rode a partir do kit (não achei ./run.sh)"; exit 1; }

MIN=${MIN:-5}
REPS=${REPS:-3}
FINAL=${FINAL:-ctf.py}
ANTERIOR=${ANTERIOR:-ctf_v1.py}
SO=${SO:-}
REINICIAR=${REINICIAR:-1}
STAMP=${PASTA:-$(date +%Y%m%d-%H%M)}
OUT_HOST="exercicios/ctf/partidas/$STAMP"
OUT_CT="/ws/psr_exercicios/ctf/partidas/$STAMP"
mkdir -p "$OUT_HOST"

CONFRONTOS=(
  "final_x_parado   $FINAL     none"
  "parado_x_final   none       $FINAL"
  "final_x_v1       $FINAL     $ANTERIOR"
  "v1_x_final       $ANTERIOR  $FINAL"
)

parar_ros() { docker rm -f psrkit-ros >/dev/null 2>&1 || true; }

abrir_sim() {  # reabre o simulador; o visualizador às vezes falha logo depois de fechar o anterior
  local tentativa
  for tentativa in 1 2 3; do
    if [ "$REINICIAR" = 1 ] || [ "$tentativa" -gt 1 ]; then
      ./run.sh down >/dev/null
      sleep $((3 * tentativa))  # dá tempo de a janela anterior ser liberada
    fi
    if ./run.sh sim ctf; then return 0; fi
    echo "[partidas] o simulador não abriu (tentativa $tentativa de 3)"
  done
  return 1
}
FALHAS=()
trap 'echo; echo "[partidas] interrompido"; parar_ros; exit 130' INT TERM

for linha in "${CONFRONTOS[@]}"; do
  read -r nome azul vermelho <<<"$linha"
  if [ -n "$SO" ] && [[ "$nome" != *"$SO"* ]]; then continue; fi
  for i in $(seq 1 "$REPS"); do
    rotulo="${nome}_${i}"
    echo "[partidas] ===== $rotulo: azul=$azul vermelho=$vermelho ($MIN min) ====="
    parar_ros
    if ! abrir_sim; then
      echo "[partidas] pulando $rotulo: o simulador não abriu depois de 3 tentativas"
      FALHAS+=("$rotulo")
      continue
    fi

    ./run.sh run ctf "blue:=$azul" "red:=$vermelho" </dev/null >"$OUT_HOST/${rotulo}_launch.log" 2>&1 &
    pid=$!
    for _ in $(seq 1 60); do  # espera o container ROS subir
      docker inspect -f '{{.State.Running}}' psrkit-ros 2>/dev/null | grep -q true && break
      sleep 1
    done
    sleep 3
    docker exec psrkit-ros /ros-entrypoint.sh python3 /ws/psr_exercicios/ctf/ctf_logger.py \
      --minutes "$MIN" --label "$rotulo" --blue "$azul" --red "$vermelho" --out "$OUT_CT" \
      | grep --line-buffered -E "RESULTADO|ponto|segurado|ERROR|erro" || true
    # arquivos criados pelo container (root) passam a ser do usuário
    docker exec psrkit-ros chown -R "$(id -u):$(id -g)" "$OUT_CT" 2>/dev/null || true
    parar_ros
    wait "$pid" 2>/dev/null || true
    if grep -qiE "Traceback|process has died" "$OUT_HOST/${rotulo}_launch.log"; then
      echo "[partidas] ATENÇÃO: erro em algum nó, veja $OUT_HOST/${rotulo}_launch.log"
    fi
  done
done

echo
if [ ${#FALHAS[@]} -gt 0 ]; then
  echo "[partidas] partidas que não rodaram: ${FALHAS[*]}"
  echo "[partidas] para completá-las: PASTA=$STAMP SO=<nome do confronto> ./exercicios/ctf/rodar_partidas.sh"
fi
echo "[partidas] pronto: $OUT_HOST/resumo.csv"
column -s, -t <"$OUT_HOST/resumo.csv" 2>/dev/null | cut -c1-160 || cat "$OUT_HOST/resumo.csv"
