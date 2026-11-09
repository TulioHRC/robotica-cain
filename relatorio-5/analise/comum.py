import glob
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERMELHO = "#960B22"
DOURADO = "#C4A35A"
CINZA = "#5C5757"
AZUL = "#1F6FB2"
MM = 1 / 25.4

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Arimo", "Liberation Sans", "Helvetica", "DejaVu Sans"],
    "font.size": 8,
    "axes.titlesize": 8,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "axes.edgecolor": CINZA,
    "axes.labelcolor": "#1A1A1A",
    "xtick.color": CINZA,
    "ytick.color": CINZA,
    "axes.grid": True,
    "grid.color": "#E4E4E4",
    "grid.linewidth": 0.5,
    "axes.axisbelow": True,
    "axes.formatter.use_locale": False,
    "pdf.fonttype": 42,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})


def virgula(x, casas=2):
    return ("%.*f" % (casas, x)).replace(".", ",")


def formatador(casas=1):
    return matplotlib.ticker.FuncFormatter(lambda x, _: virgula(x, casas))


def arquivos(padrao, explicitos, duracao):
    lista = explicitos if explicitos else sorted(glob.glob(os.path.join(RAIZ, padrao)))
    validos = []
    for caminho in lista:
        df = pd.read_csv(caminho)
        if len(df) and df["t"].iloc[-1] >= 0.98 * duracao:
            validos.append(caminho)
        else:
            print("ignorado (ensaio incompleto):", os.path.relpath(caminho, RAIZ))
    return validos


def distancia(df):
    return float(np.hypot(np.diff(df["x"]), np.diff(df["y"])).sum())


def arena(ax, cilindro):
    ax.add_patch(plt.Rectangle((-1, -1), 2, 2, fill=False, ec=CINZA, lw=2.0))
    if cilindro:
        ax.add_patch(plt.Circle((0, 0), 0.15, fc="#E8A08A", ec=VERMELHO, lw=0.8))
    ax.set_xlim(-1.06, 1.06)
    ax.set_ylim(-1.06, 1.06)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.xaxis.set_major_formatter(formatador(1))
    ax.yaxis.set_major_formatter(formatador(1))


def salvar(fig, saida, nome):
    pasta = os.path.join(saida, "figs")
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, nome)
    fig.savefig(caminho)
    plt.close(fig)
    print("figura:", os.path.relpath(caminho, RAIZ))


def media(valores, casas):
    v = np.array(valores, dtype=float)
    if len(v) == 1 or np.allclose(v, v[0]):
        return virgula(v[0], 0 if float(v[0]).is_integer() else casas)
    return "%s $\\pm$ %s" % (virgula(v.mean(), casas), virgula(v.std(ddof=1), casas))


def tabela_latex(saida, nome, legenda, rotulo, cabecalho, linhas, nota):
    pasta = os.path.join(saida, "dados")
    os.makedirs(pasta, exist_ok=True)
    texto = [
        "\\begin{table}[htbp]",
        "  \\centering",
        "  \\caption{%s}" % legenda,
        "  \\label{%s}" % rotulo,
        "  \\begin{tabelapsr}{@{\\hspace{6pt}}X c c@{\\hspace{6pt}}}",
        "    \\linhacab " + " & ".join("\\cab{%s}" % c for c in cabecalho) + " \\\\ \\hline",
    ]
    for linha in linhas:
        texto.append("    " + " & ".join(linha) + " \\\\ \\hline")
    texto.append("  \\end{tabelapsr}")
    if nota:
        texto.append("  \\par\\vspace{2pt}{\\footnotesize\\color{psrgray}%s\\par}" % nota)
    texto.append("\\end{table}")
    caminho = os.path.join(pasta, nome)
    with open(caminho, "w") as f:
        f.write("\n".join(texto) + "\n")
    print("tabela:", os.path.relpath(caminho, RAIZ))
