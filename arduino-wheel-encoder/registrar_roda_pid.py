#!/usr/bin/env python3
"""
Registra os ensaios do PID (roda_pid.ino) em CSV e gera os gráficos do relatório.

Cada ensaio que o Arduino manda entre "INICIO <nome>" e "FIM" vira
registros/<nome>_<data>.csv e registros/<nome>_<data>.png, com setpoint,
velocidade bruta e filtrada, pulso e distância.

Digite os comandos no terminal + Enter: v 100, 1, 2, kp 1.5, ki 3...
Todos os ensaios terminam sozinhos (s para antes da hora). Ctrl+C encerra o script.

Uso:
    python plot_roda_pid.py COM4
    python plot_roda_pid.py --grafico registros\\patamares_xxx.csv   (refaz o gráfico)
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


def metricas_por_trecho(t, sp, v):
    """Para cada trecho de setpoint constante e diferente de zero: erro em regime,
    sobressinal e tempo ate 90% do setpoint, contados a partir da troca."""
    trechos, ini = [], 0
    for i in range(1, len(sp) + 1):
        if i == len(sp) or sp[i] != sp[ini]:
            trechos.append((ini, i - 1))
            ini = i
    linhas = []
    for a, b in trechos:
        alvo = sp[a]
        if alvo == 0 or t[b] - t[a] < 0.8:
            continue
        sinal = 1 if alvo > 0 else -1
        idx = range(a, b + 1)
        fim = [i for i in idx if t[i] >= t[b] - 1.0]
        media = sum(v[i] for i in fim) / len(fim)
        pico = max(sinal * v[i] for i in idx)
        sobre = max(0.0, (pico / abs(alvo) - 1) * 100)
        t90 = next((t[i] - t[a] for i in idx if sinal * v[i] >= 0.9 * abs(alvo)), None)
        linhas.append((alvo, media, alvo - media, sobre, t90))
    return linhas


def grafico_pid(caminho, nome):
    config, c = ler_csv(caminho)
    t = [x / 1000 for x in c["t_ms"]]
    neutro = float(config.get("neutro_us", 1495))

    fig, (ax_v, ax_p, ax_s) = plt.subplots(
        3, 1, sharex=True, figsize=(9, 8),
        gridspec_kw={"height_ratios": [3, 1.3, 1.3]})

    ax_v.plot(t, c["v_bruta"], color="lightgray", lw=1.0, label="velocidade bruta")
    ax_v.step(t, c["setpoint"], where="post", color="k", ls="--", lw=1.3, label="setpoint")
    ax_v.plot(t, c["v_filtrada"], color="#960B22", lw=1.7, label="velocidade filtrada")
    ax_v.set_ylabel("velocidade (mm/s)")
    ax_v.set_title(f"PID de velocidade — ensaio: {nome}")
    ax_v.grid(True, alpha=0.4)
    ax_v.legend(loc="upper left")

    ax_p.plot(t, c["pulso_us"], color="#2B6CB0", lw=1.2, label="pulso comandado")
    ax_p.axhline(neutro, color="k", lw=0.8, label=f"neutro {neutro:.0f} µs")
    ax_p.axhline(neutro + 250, color="gray", ls=":", lw=1, label="limite ±250 µs")
    ax_p.axhline(neutro - 250, color="gray", ls=":", lw=1)
    ax_p.set_ylabel("pulso (µs)")
    ax_p.grid(True, alpha=0.4)
    ax_p.legend(loc="upper left", fontsize=8)

    ax_s.plot(t, c["s_mm"], color="#2F855A", lw=1.4)
    ax_s.set_ylabel("distância s (mm)")
    ax_s.set_xlabel("tempo (s)")
    ax_s.grid(True, alpha=0.4)

    s_final = c["s_mm"][-1]
    ax_s.annotate(f"s final = {s_final:.0f} mm", xy=(t[-1], s_final), xytext=(-8, 8),
                  textcoords="offset points", ha="right", fontsize=9)

    rodape(fig, config)
    salvar(fig, caminho)

    print(f"\n>>> Distância final: {s_final:.1f} mm  (ticks finais: {c['ticks'][-1]:.0f})")
    linhas = metricas_por_trecho(t, c["setpoint"], c["v_filtrada"])
    if linhas:
        print(">>> Por trecho (use no texto do relatório):")
        print("      setpoint  v_regime   erro  sobressinal  t90%")
        for alvo, media, erro, sobre, t90 in linhas:
            t90s = f"{t90:.2f} s" if t90 is not None else "não chegou"
            print(f"      {alvo:7.0f}  {media:8.1f} {erro:6.1f}  {sobre:8.1f} %  {t90s}")
    print()


def rodape(fig, config):
    texto = "  ".join(f"{k}={v}" for k, v in config.items())
    fig.text(0.01, 0.005, texto, fontsize=7, color="gray")
    fig.tight_layout(rect=(0, 0.03, 1, 1))


def salvar(fig, caminho):
    png = os.path.abspath(os.path.splitext(caminho)[0] + ".png")
    fig.savefig(png, dpi=150)
    plt.close(fig)
    print(f">>> Gráfico salvo em {png}", flush=True)
    abrir_arquivo(png)


def abrir_arquivo(caminho):
    """Abre o PNG no visualizador padrão do sistema."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(caminho)
        elif sys.platform == "darwin":
            os.system(f'open "{caminho}"')
        else:
            os.system(f'xdg-open "{caminho}" >/dev/null 2>&1 &')
    except Exception:
        pass


def gerar_grafico(caminho, nome=None):
    """Escolhe o gráfico pelo nome do ensaio (ou pelo nome do arquivo)."""
    if nome is None:
        nome = os.path.splitext(os.path.basename(caminho))[0].split("_")[0]
    try:
        if nome in ("patamares", "inversao", "manual"):
            grafico_pid(caminho, nome)
        else:
            print(f">>> Não sei qual gráfico fazer para '{nome}'.")
    except Exception:
        import traceback
        print(">>> Não consegui gerar o gráfico:")
        traceback.print_exc()


# ---------------------------------------------------------------
def thread_teclado(ser):
    for linha in sys.stdin:
        try:
            ser.write((linha.strip() + "\n").encode())
        except serial.SerialException:
            break


def main():
    # Refazer o gráfico de um CSV já salvo:  python registrar.py --grafico registros\patamares_xxx.csv
    if len(sys.argv) > 2 and sys.argv[1] == "--grafico":
        gerar_grafico(sys.argv[2])
        return

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
    print(f"Lendo {porta}. Ctrl+C sai.")
    print("Comandos: v <mm/s> [segundos], 1 (patamares), 2 (inversão), s (para antes), kp/ki/kd <x>, neutro <us>, b <us>, ?")
    print(f"Os arquivos vão para: {os.path.abspath(PASTA)}")

    arquivo, caminho, nome = None, None, None
    avisou_codigo_errado = False
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
                print(f">>> Gravando {caminho}. O gráfico sai quando o ensaio terminar (linha FIM).")
            elif linha == "FIM" and arquivo:
                arquivo.close()
                arquivo = None
                print(f">>> Registro salvo em {os.path.abspath(caminho)}")
                gerar_grafico(caminho, nome)
            elif arquivo:
                arquivo.write(linha + "\n")
            elif "setpoint:" in linha and not avisou_codigo_errado:
                print(">>> ATENÇÃO: a Mega está com um código antigo (formato setpoint:...). "
                      "Grave o roda_pid.ino para usar 1, 2 e v.")
                avisou_codigo_errado = True
    except KeyboardInterrupt:
        pass
    finally:
        if arquivo:
            arquivo.close()
            print(f"\n>>> Ensaio interrompido; gerando gráfico do que foi gravado.")
            gerar_grafico(caminho, nome)
        ser.close()


if __name__ == "__main__":
    main()