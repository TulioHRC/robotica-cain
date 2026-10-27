#!/usr/bin/env python3

"""
Plota ao vivo os dados recebidos pela serial da Mega.
Focado em duas variáveis: Velocidade Bruta e Velocidade Filtrada.

Uso:
    python3 plot_serial.py /dev/ttyUSB0
"""

import sys
import time
from collections import deque

import matplotlib.pyplot as plt
import serial

BAUD_RATE = 115200
MAX_AMOSTRAS = 150
TEMPO_INICIALIZACAO = 2

def obter_porta():
    """Obtém a porta serial informada pela linha de comando."""
    return sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"

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
    Interpreta uma linha recebida pela serial esperando 2 valores:
    bruta,filtrada
    """
    partes = linha.split(",")
    if len(partes) != 2:
        return None

    try:
        bruta = float(partes[0])
        filtrada = float(partes[1])
        return bruta, filtrada
    except ValueError:
        return None

def configurar_grafico():
    """Cria e configura o gráfico com duas linhas."""
    plt.ion()
    figura, eixo = plt.subplots()

    # Linha para velocidade bruta (ruído em cinza)
    linha_bruta, = eixo.plot([], [], color="lightgray", linewidth=1.0, label="Bruta (Ruído)")
    
    # Linha para velocidade filtrada (sinal útil em vermelho)
    linha_filtrada, = eixo.plot([], [], color="#960B22", linewidth=1.5, label="Filtrada (Média)")

    eixo.set_xlabel("amostra")
    eixo.set_ylabel("velocidade (mm/s)")
    eixo.set_title("Filtro de Velocidade da Roda")
    eixo.legend(loc="upper right")
    eixo.grid(True)
    
    figura.tight_layout()

    return figura, eixo, linha_bruta, linha_filtrada

def atualizar_grafico(eixo, linha_bruta, linha_filtrada, xs, ys_bruta, ys_filtrada):
    """Atualiza os dados exibidos no gráfico e trava a escala no sinal filtrado."""
    linha_bruta.set_data(xs, ys_bruta)
    linha_filtrada.set_data(xs, ys_filtrada)

    # Ajusta o eixo X para acompanhar as amostras recentes
    eixo.set_xlim(max(0, xs[-1] - MAX_AMOSTRAS), max(MAX_AMOSTRAS, xs[-1] + 5))

    # Ajusta o eixo Y baseando-se APENAS na velocidade filtrada
    if len(ys_filtrada) > 0:
        min_val = min(ys_filtrada)
        max_val = max(ys_filtrada)
        # Margem de segurança de 20% (ou pelo menos 2mm/s)
        margem = max(2.0, (max_val - min_val) * 0.2)
        eixo.set_ylim(min_val - margem, max_val + margem)

    plt.pause(0.001)

def main():
    porta = obter_porta()
    
    try:
        ser = abrir_serial(porta)
    except Exception as e:
        print(f"Erro ao abrir a porta {porta}: {e}")
        sys.exit(1)

    xs = deque(maxlen=MAX_AMOSTRAS)
    ys_bruta = deque(maxlen=MAX_AMOSTRAS)
    ys_filtrada = deque(maxlen=MAX_AMOSTRAS)

    numero_amostra = 0
    _, eixo, linha_bruta, linha_filtrada = configurar_grafico()

    try:
        while True:
            cru = ser.readline().decode(errors="ignore").strip()
            if not cru:
                continue

            amostra = interpretar_amostra(cru)
            if amostra is None:
                continue

            bruta, filtrada = amostra
            numero_amostra += 1

            xs.append(numero_amostra)
            ys_bruta.append(bruta)
            ys_filtrada.append(filtrada)

            print(f"Cru: {cru}", flush=True)

            atualizar_grafico(
                eixo,
                linha_bruta,
                linha_filtrada,
                xs,
                ys_bruta,
                ys_filtrada
            )

    except KeyboardInterrupt:
        pass
    finally:
        ser.close()

if __name__ == "__main__":
    main()