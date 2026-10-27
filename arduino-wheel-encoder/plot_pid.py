#!/usr/bin/env python3
"""
Plota ao vivo os dados do PID da roda recebidos pela serial da Mega
e salva tudo em CSV para os gráficos do relatório.

Entende os dois formatos que o Arduino imprime:
  - código PID simples:  setpoint:150 velocidade:142.3 pulso:85
  - roda_pid.ino (CSV):  t_ms,setpoint,v_bruta,v_filtrada,u_us,pulso_us,s_mm

Enquanto roda, digite no terminal e dê Enter para mandar ao Arduino
(ex.: 150, -150, 0 no código simples; ou 1, 2, c, s, kp 1.5 no roda_pid.ino).
Ctrl+C encerra e salva o CSV.

Uso:
    python3 plot_pid.py /dev/ttyUSB0      (Linux)
    python  plot_pid.py COM3              (Windows)
"""

import csv
import sys
import threading
import time
from collections import deque
from datetime import datetime

import matplotlib.pyplot as plt
import serial

BAUD_RATE = 115200
JANELA_S = 15            # segundos visíveis no gráfico
TEMPO_INICIALIZACAO = 2  # a Mega reinicia ao abrir a serial
INTERVALO_DESENHO = 0.1  # redesenha no máximo a cada 0,1 s

# Nomes possíveis de cada variável nos dois formatos
ALIASES = {
    "setpoint": ["setpoint"],
    "velocidade": ["velocidade", "v_filtrada", "filtrada"],
    "bruta": ["bruta", "v_bruta"],
    "pulso": ["pulso", "u_us"],
    "s_mm": ["s_mm"],
}


def obter_porta():
    return sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"


def abrir_serial(porta):
    conexao = serial.Serial(porta, BAUD_RATE, timeout=1)
    time.sleep(TEMPO_INICIALIZACAO)
    conexao.reset_input_buffer()
    return conexao


def normalizar(valores):
    """Converte os nomes recebidos para os nomes padrão do script."""
    saida = {}
    for padrao, nomes in ALIASES.items():
        for nome in nomes:
            if nome in valores:
                saida[padrao] = valores[nome]
                break
    return saida


class Interpretador:
    """Lê linhas no formato 'nome:valor nome:valor' ou CSV com cabeçalho."""

    def __init__(self):
        self.cabecalho = None

    def interpretar(self, linha):
        if not linha or linha.startswith("#"):
            return None

        # Formato "nome:valor"
        if ":" in linha:
            valores = {}
            for par in linha.replace(",", " ").split():
                if ":" not in par:
                    continue
                nome, valor = par.split(":", 1)
                try:
                    valores[nome.strip()] = float(valor)
                except ValueError:
                    pass
            return normalizar(valores) or None

        # Formato CSV
        partes = [p.strip() for p in linha.split(",")]
        try:
            numeros = [float(p) for p in partes]
        except ValueError:
            self.cabecalho = partes  # linha de cabeçalho
            return None
        if self.cabecalho and len(self.cabecalho) == len(numeros):
            return normalizar(dict(zip(self.cabecalho, numeros))) or None
        return None


def thread_teclado(ser):
    """Manda para o Arduino o que for digitado no terminal."""
    for linha in sys.stdin:
        try:
            ser.write((linha.strip() + "\n").encode())
            print(f">> enviado: {linha.strip()}", flush=True)
        except serial.SerialException:
            break


def configurar_grafico():
    plt.ion()
    figura, (eixo_v, eixo_p) = plt.subplots(2, 1, sharex=True, figsize=(9, 6))

    linhas = {
        "bruta": eixo_v.plot([], [], color="lightgray", lw=1.0, label="velocidade bruta")[0],
        "setpoint": eixo_v.plot([], [], "k--", lw=1.2, label="setpoint")[0],
        "velocidade": eixo_v.plot([], [], color="#960B22", lw=1.6, label="velocidade filtrada")[0],
        "pulso": eixo_p.plot([], [], color="#2B6CB0", lw=1.2, label="correção do pulso")[0],
    }

    eixo_v.set_ylabel("velocidade (mm/s)")
    eixo_v.set_title("PID de velocidade da roda")
    eixo_v.legend(loc="upper left")
    eixo_v.grid(True)

    eixo_p.set_xlabel("tempo (s)")
    eixo_p.set_ylabel("pulso − neutro (µs)")
    eixo_p.legend(loc="upper left")
    eixo_p.grid(True)

    figura.tight_layout()
    return figura, eixo_v, eixo_p, linhas


def atualizar_grafico(eixo_v, eixo_p, linhas, ts, dados):
    for nome, linha in linhas.items():
        ys = dados[nome]
        if len(ys) == len(ts) and ys:
            linha.set_data(ts, ys)

    t_fim = ts[-1]
    eixo_v.set_xlim(max(0, t_fim - JANELA_S), max(JANELA_S, t_fim + 0.5))

    # Escala de velocidade pelo setpoint e pela filtrada (a bruta é ruidosa)
    ref = list(dados["velocidade"]) + list(dados["setpoint"])
    if ref:
        lo, hi = min(ref), max(ref)
        margem = max(5.0, (hi - lo) * 0.2)
        eixo_v.set_ylim(lo - margem, hi + margem)

    if dados["pulso"]:
        lo, hi = min(dados["pulso"]), max(dados["pulso"])
        margem = max(10.0, (hi - lo) * 0.2)
        eixo_p.set_ylim(lo - margem, hi + margem)

    plt.pause(0.001)


def main():
    porta = obter_porta()
    try:
        ser = abrir_serial(porta)
    except Exception as e:
        print(f"Erro ao abrir a porta {porta}: {e}")
        print("Feche o Monitor Serial da IDE/VS Code e confira o nome da porta.")
        sys.exit(1)

    threading.Thread(target=thread_teclado, args=(ser,), daemon=True).start()

    nome_csv = datetime.now().strftime("ensaio_%Y%m%d_%H%M%S.csv")
    arquivo = open(nome_csv, "w", newline="")
    gravador = csv.writer(arquivo)
    gravador.writerow(["t_s", "setpoint", "velocidade", "bruta", "pulso", "s_mm"])

    maxlen = 2000
    ts = deque(maxlen=maxlen)
    dados = {nome: deque(maxlen=maxlen) for nome in ALIASES}

    interp = Interpretador()
    _, eixo_v, eixo_p, linhas = configurar_grafico()
    t0 = time.time()
    ultimo_desenho = 0.0

    print(f"Lendo {porta}. Digite comandos + Enter. Ctrl+C para sair.", flush=True)

    try:
        while True:
            cru = ser.readline().decode(errors="ignore").strip()
            if not cru:
                plt.pause(0.001)
                continue

            amostra = interp.interpretar(cru)
            if amostra is None:
                print(cru, flush=True)  # mensagens do Arduino (# ...)
                continue

            t = time.time() - t0
            ts.append(t)
            for nome in ALIASES:
                if nome in amostra:
                    dados[nome].append(amostra[nome])

            gravador.writerow([f"{t:.3f}"] + [amostra.get(n, "") for n in
                              ["setpoint", "velocidade", "bruta", "pulso", "s_mm"]])

            if time.time() - ultimo_desenho > INTERVALO_DESENHO:
                atualizar_grafico(eixo_v, eixo_p, linhas, ts, dados)
                ultimo_desenho = time.time()

    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        arquivo.close()
        print(f"\nDados salvos em {nome_csv}")


if __name__ == "__main__":
    main()