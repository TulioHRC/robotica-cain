#!/usr/bin/env python3

"""
Plota ao vivo os dados recebidos pela serial da Mega.

Formatos aceitos:
    Uma coluna: sinal cru
        123
        456

    Duas colunas: sinal, distância em milímetros
        123,10.5
        456,12.3

Uso:
    python3 plot_serial.py /dev/ttyACM0
"""

import sys
import time
from collections import deque

import matplotlib.pyplot as plt
import serial


BAUD_RATE = 115200
MAX_AMOSTRAS = 200
TEMPO_INICIALIZACAO = 2


def obter_porta():
    """Obtém a porta serial informada pela linha de comando."""
    return sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"


def abrir_serial(porta):
    """Abre a conexão serial e aguarda a inicialização da Mega."""
    conexao = serial.Serial(
        porta,
        BAUD_RATE,
        timeout=1,
    )

    time.sleep(TEMPO_INICIALIZACAO)

    return conexao


def interpretar_amostra(linha):
    """
    Interpreta uma linha recebida pela serial.

    Retorna:
        ("cru", valor) para sinal cru
        ("mm", valor) para distância
        None para dados inválidos
    """
    if linha.isdigit():
        return "cru", float(linha)

    partes = linha.split(",")

    if len(partes) != 2:
        return None

    try:
        distancia = float(partes[1])
    except ValueError:
        return None

    return "mm", distancia


def configurar_grafico():
    """Cria e configura o gráfico."""
    plt.ion()

    figura, eixo = plt.subplots()

    linha, = eixo.plot(
        [],
        [],
        color="#960B22",
        linewidth=1.5,
    )

    eixo.set_xlabel("amostra")
    figura.tight_layout()

    return figura, eixo, linha


def atualizar_grafico(eixo, linha, xs, ys):
    """Atualiza os dados exibidos no gráfico."""
    linha.set_data(xs, ys)

    eixo.relim()
    eixo.autoscale_view()

    plt.pause(0.001)


def main():
    porta = obter_porta()
    ser = abrir_serial(porta)

    xs = deque(maxlen=MAX_AMOSTRAS)
    ys = deque(maxlen=MAX_AMOSTRAS)

    numero_amostra = 0
    modo = None

    _, eixo, linha = configurar_grafico()

    try:
        while True:
            bruto = ser.readline().decode(errors="ignore").strip()
            amostra = interpretar_amostra(bruto)

            if amostra is None:
                continue

            tipo, valor = amostra

            # O primeiro tipo válido determina o modo do gráfico.
            if modo is None:
                modo = tipo

                if modo == "mm":
                    eixo.set_ylabel("distância (mm)")
                else:
                    eixo.set_ylabel("sinal (contagens)")

            # Ignora dados de um formato diferente do inicial.
            if tipo != modo:
                continue

            numero_amostra += 1

            xs.append(numero_amostra)
            ys.append(valor)

            print(bruto, flush=True)

            atualizar_grafico(
                eixo,
                linha,
                xs,
                ys,
            )

    except KeyboardInterrupt:
        pass

    finally:
        ser.close()


if __name__ == "__main__":
    main()