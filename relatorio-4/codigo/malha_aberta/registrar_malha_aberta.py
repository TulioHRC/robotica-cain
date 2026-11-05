#!/usr/bin/env python3
"""
Registra os ensaios da Mega em CSV e gera os gráficos do relatório.

Cada ensaio que o Arduino manda entre "INICIO <nome>" e "FIM" vira
registros/<nome>_<data>.csv e registros/<nome>_<data>.png.

Digite os comandos no terminal + Enter (n, c, f 1600, neutro 1490, s...).
Ctrl+C encerra.

Uso:
    python registrar.py COM4
"""

import os
import sys
import threading
import time
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # salva PNG sem travar a leitura da serial
import matplotlib.pyplot as plt
import serial

BAUD_RATE = 115200
PASTA = "registros"


# ---------------------------------------------------------------
def ler_csv(caminho):
    """Lê o CSV salvo, ignorando as linhas de comentário (#)."""
    config, cabecalho, linhas = {}, None, []
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            if linha.startswith("#"):
                for par in linha[1:].split():
                    if "=" in par:
                        k, v = par.split("=", 1)
                        config[k] = v
                continue
            if cabecalho is None:
                cabecalho = linha.split(",")
                continue
            try:
                linhas.append([float(x) for x in linha.split(",")])
            except ValueError:
                pass
    colunas = {nome: [l[i] for l in linhas] for i, nome in enumerate(cabecalho or [])}
    return config, colunas


def achar_banda_morta(pulsos, ticks):
    """Faixa contínua de pulsos com a roda parada (|ticks| <= 1) mais perto de 1500."""
    parados = sorted(p for p, t in zip(pulsos, ticks) if abs(t) <= 1)
    if not parados:
        return None
    passo = min(b - a for a, b in zip(sorted(pulsos), sorted(pulsos)[1:]))
    blocos, atual = [], [parados[0]]
    for p in parados[1:]:
        if p - atual[-1] <= passo + 0.5:
            atual.append(p)
        else:
            blocos.append(atual)
            atual = [p]
    blocos.append(atual)
    bloco = min(blocos, key=lambda b: min(abs(p - 1500) for p in b))
    return bloco[0], bloco[-1]


# ---------------------------------------------------------------
def grafico_varredura(caminho, nome):
    config, c = ler_csv(caminho)
    pulsos, ticks, vel = c["pulso_us"], c["ticks"], c["v_mm_s"]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(pulsos, vel, "o-", color="#960B22", ms=4, lw=1.2, label="velocidade em regime")

    banda = achar_banda_morta(pulsos, ticks)
    if banda:
        a, b = banda
        neutro = round((a + b) / 2)
        ax.axvspan(a, b, color="orange", alpha=0.25, label=f"banda morta {a:.0f}–{b:.0f} µs")
        ax.axvline(neutro, color="k", ls="--", lw=1, label=f"neutro ≈ {neutro} µs")
        print(f"\n>>> Roda parada de {a:.0f} a {b:.0f} µs. "
              f"Neutro ≈ {neutro} µs, meia-largura da banda ≈ {(b - a) / 2:.0f} µs.")
        if nome == "neutro":
            print(f">>> Grave no Arduino com:  neutro {neutro}   "
                  f"(e troque NEUTRO_US no código)\n")

    if nome == "curva" and vel:
        print(f">>> Velocidade máxima: +{max(vel):.1f} mm/s / {min(vel):.1f} mm/s\n")

    ax.axhline(0, color="gray", lw=0.8)
    ax.set_xlabel("largura do pulso (µs)")
    ax.set_ylabel("velocidade da roda (mm/s)")
    titulo = "Busca do neutro" if nome == "neutro" else "Curva pulso × velocidade (malha aberta)"
    ax.set_title(titulo)
    ax.grid(True, alpha=0.4)
    ax.legend()
    rodape(fig, config)
    salvar(fig, caminho)


def grafico_filtros(caminho):
    config, c = ler_csv(caminho)
    t = [x / 1000 for x in c["t_ms"]]

    fig, (ax_v, ax_p) = plt.subplots(2, 1, sharex=True, figsize=(9, 6),
                                     gridspec_kw={"height_ratios": [3, 1]})
    ax_v.plot(t, c["v_bruta"], color="lightgray", lw=1.2, label="bruta (Δs/Δt)")
    ax_v.plot(t, c["v_media"], color="#2B6CB0", lw=1.6,
              label=f"média móvel (janela {config.get('janela_media', '?')})")
    ax_v.plot(t, c["v_passabaixa"], color="#960B22", lw=1.6,
              label=f"passa-baixa (α = {config.get('alpha', '?')})")
    ax_v.set_ylabel("velocidade (mm/s)")
    ax_v.set_title(f"Comparação de filtros — degrau de {config.get('pulso_degrau_us', '?')} µs")
    ax_v.grid(True, alpha=0.4)
    ax_v.legend()

    ax_p.step(t, c["pulso_us"], where="post", color="k", lw=1.2)
    ax_p.set_ylabel("pulso (µs)")
    ax_p.set_xlabel("tempo (s)")
    ax_p.grid(True, alpha=0.4)
    rodape(fig, config)
    salvar(fig, caminho)


def rodape(fig, config):
    texto = "  ".join(f"{k}={v}" for k, v in config.items())
    fig.text(0.01, 0.005, texto, fontsize=7, color="gray")
    fig.tight_layout(rect=(0, 0.03, 1, 1))


def salvar(fig, caminho):
    png = os.path.splitext(caminho)[0] + ".png"
    fig.savefig(png, dpi=150)
    plt.close(fig)
    print(f">>> Gráfico salvo em {png}", flush=True)


# ---------------------------------------------------------------
def thread_teclado(ser):
    for linha in sys.stdin:
        try:
            ser.write((linha.strip() + "\n").encode())
        except serial.SerialException:
            break


def main():
    porta = sys.argv[1] if len(sys.argv) > 1 else "COM4"
    try:
        ser = serial.Serial(porta, BAUD_RATE, timeout=1)
    except Exception as e:
        print(f"Erro ao abrir {porta}: {e}")
        print("Feche o Monitor Serial e qualquer outro script usando a porta.")
        sys.exit(1)
    time.sleep(2)
    os.makedirs(PASTA, exist_ok=True)
    threading.Thread(target=thread_teclado, args=(ser,), daemon=True).start()
    print(f"Lendo {porta}. Comandos: n, c, f <pulso>, p <pulso>, neutro <us>, s. Ctrl+C sai.")

    arquivo, caminho, nome = None, None, None
    try:
        while True:
            linha = ser.readline().decode(errors="ignore").strip()
            if not linha:
                continue
            print(linha, flush=True)

            if linha.startswith("INICIO"):
                nome = linha.split(maxsplit=1)[1] if " " in linha else "ensaio"
                carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
                caminho = os.path.join(PASTA, f"{nome}_{carimbo}.csv")
                arquivo = open(caminho, "w", encoding="utf-8")
            elif linha == "FIM" and arquivo:
                arquivo.close()
                arquivo = None
                print(f">>> Registro salvo em {caminho}")
                try:
                    if nome in ("neutro", "curva"):
                        grafico_varredura(caminho, nome)
                    elif nome == "filtros":
                        grafico_filtros(caminho)
                except Exception as e:
                    print(f">>> Não consegui gerar o gráfico: {e}")
            elif arquivo:
                arquivo.write(linha + "\n")
    except KeyboardInterrupt:
        pass
    finally:
        if arquivo:
            arquivo.close()
        ser.close()


if __name__ == "__main__":
    main()