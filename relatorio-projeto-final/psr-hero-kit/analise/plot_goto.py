import argparse
import math
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from comum import (AZUL, DOURADO, MM, RAIZ, VERMELHO, arena, arquivos, distancia, formatador,
                   media, salvar, tabela_latex)

DURACAO = 180.0


def metas(df):
    troca = (df["xg"].diff().abs() > 1e-6) | (df["yg"].diff().abs() > 1e-6)
    idx = np.flatnonzero(troca.to_numpy())
    inicios = np.r_[0, idx]
    t = df["t"].to_numpy()
    chegadas = t[idx]
    dt = np.diff(np.r_[t[0], chegadas])
    rho0 = df["rho"].to_numpy()[inicios[:len(idx)]]
    atingidas = df[["xg", "yg"]].to_numpy()[inicios[:len(idx)]]
    return idx, chegadas, dt, rho0, atingidas


def metricas(df):
    idx, chegadas, dt, rho0, _ = metas(df)
    placar = int(df["metas"].iloc[-1] - df["metas"].iloc[0]) if df["metas"].iloc[0] >= 0 else -1
    if placar >= 0 and placar != len(idx):
        print("aviso: o placar indica %d metas e a troca de metas indica %d" % (placar, len(idx)))
    return {
        "M": len(idx),
        "dt": dt.mean() if len(dt) else float("nan"),
        "dp": dt.std(ddof=1) if len(dt) > 1 else float("nan"),
        "norm": (dt / rho0).mean() if len(dt) else float("nan"),
        "L": distancia(df),
    }, dt, dt / rho0


def trajetoria(df, saida, nome, largura):
    _, _, _, _, atingidas = metas(df)
    fig, ax = plt.subplots(figsize=(largura * MM, largura * 0.9 * MM))
    arena(ax, False)
    ax.plot(df["x"], df["y"], color=AZUL, lw=0.5, alpha=0.85)
    for k, (gx, gy) in enumerate(atingidas, start=1):
        ax.add_patch(plt.Circle((gx, gy), 0.06, fc="none", ec=VERMELHO, lw=0.7))
        ax.text(gx, gy, str(k), ha="center", va="center", fontsize=4.5, color=VERMELHO)
    ax.add_patch(plt.Circle((df["xg"].iloc[-1], df["yg"].iloc[-1]), 0.06, fc="none", ec=VERMELHO,
                            lw=0.7, ls="--"))
    ax.plot(df["x"].iloc[0], df["y"].iloc[0], "o", color=DOURADO, ms=5, mec="k", mew=0.4, label="partida")
    ax.plot([], [], "o", mfc="none", mec=VERMELHO, label="meta atingida (%d)" % len(atingidas))
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False)
    salvar(fig, saida, nome)


def rho_alpha(df, saida):
    _, chegadas, _, _, _ = metas(df)
    fig, (a1, a2) = plt.subplots(2, 1, sharex=True, figsize=(165 * MM, 70 * MM))
    a1.plot(df["t"], df["rho"], color=AZUL, lw=0.7)
    a2.plot(df["t"], df["alpha"], color=AZUL, lw=0.7)
    for t in chegadas:
        a1.axvline(t, color=DOURADO, lw=0.6)
        a2.axvline(t, color=DOURADO, lw=0.6)
    a1.set_ylabel("$\\rho$ (m)")
    a1.yaxis.set_major_formatter(formatador(1))
    a2.set_ylabel("$\\alpha$ (rad)")
    a2.set_yticks([-math.pi, -math.pi / 2, 0, math.pi / 2, math.pi])
    a2.set_yticklabels(["$-\\pi$", "$-\\pi/2$", "0", "$\\pi/2$", "$\\pi$"])
    a2.set_ylim(-math.pi - 0.2, math.pi + 0.2)
    a2.set_xlabel("t (s)")
    a2.set_xlim(0, df["t"].iloc[-1])
    fig.align_ylabels((a1, a2))
    salvar(fig, saida, "goto_rho_alpha_A.pdf")


def tempos(dta, dtb, na, nb, saida):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(85 * MM, 76 * MM))
    for ax, dados, rot in ((a1, (dta, dtb), "$\\Delta t_j$ (s)"), (a2, (na, nb), "$\\Delta t_j/\\rho_{0,j}$ (s/m)")):
        caixa = ax.boxplot(dados, widths=0.5, patch_artist=True, showfliers=True,
                           medianprops={"color": VERMELHO, "lw": 1.0},
                           flierprops={"marker": ".", "ms": 3, "mec": "#555555"})
        for c, cor in zip(caixa["boxes"], (AZUL, DOURADO)):
            c.set_facecolor(cor)
            c.set_alpha(0.6)
        ax.set_xticks([1, 2])
        ax.set_xticklabels(["A", "B"])
        ax.set_ylabel(rot)
        ax.yaxis.set_major_formatter(formatador(1))
    fig.tight_layout()
    salvar(fig, saida, "goto_tempos_AB.pdf")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--a", nargs="*")
    p.add_argument("--b", nargs="*")
    p.add_argument("--saida", default=os.path.join(RAIZ, "relatorio"))
    args = p.parse_args()
    fa = arquivos("exercicios/goto/logs/goto_A_*.csv", args.a, DURACAO)
    fb = arquivos("exercicios/goto/logs/goto_B_*.csv", args.b, DURACAO)
    if not fa or not fb:
        raise SystemExit("faltam ensaios completos de A ou de B")
    da = [pd.read_csv(f) for f in fa]
    db = [pd.read_csv(f) for f in fb]
    ra = [metricas(d) for d in da]
    rb = [metricas(d) for d in db]
    for nome, fs, rs in (("A", fa, ra), ("B", fb, rb)):
        for f, r in zip(fs, rs):
            print(nome, os.path.relpath(f, RAIZ), {k: round(v, 3) for k, v in r[0].items()})
    trajetoria(da[-1], args.saida, "goto_trajetoria_A.pdf", 89)
    trajetoria(db[-1], args.saida, "goto_trajetoria_B.pdf", 85)
    rho_alpha(da[-1], args.saida)
    tempos(np.concatenate([r[1] for r in ra]), np.concatenate([r[1] for r in rb]),
           np.concatenate([r[2] for r in ra]), np.concatenate([r[2] for r in rb]), args.saida)
    ma = [r[0] for r in ra]
    mb = [r[0] for r in rb]
    varios = len(ma) > 1 or len(mb) > 1
    campos = [
        ("Metas atingidas $M$", "M", 1 if varios else 0),
        ("Tempo médio por meta $\\overline{\\Delta t}$ (\\unit{\\second})", "dt", 2),
        ("Desvio padrão de $\\Delta t_j$ (\\unit{\\second})", "dp", 2),
        ("Tempo normalizado médio $\\Delta t_j/\\rho_{0,j}$ (\\unit{\\second\\per\\metre})", "norm", 2),
        ("Distância percorrida (\\unit{\\metre})", "L", 1),
    ]
    linhas = [[r, media([m[k] for m in ma], c), media([m[k] for m in mb], c)] for r, k, c in campos]
    nota = ""
    if varios:
        nota = "Média $\\pm$ desvio padrão de %d ensaios (A) e %d ensaios (B)." % (len(ma), len(mb))
    tabela_latex(args.saida, "tab_goto_metricas.tex",
                 "Métricas dos ensaios de \\qty{180}{\\second} do nó \\texttt{goto}.",
                 "tab:goto-metricas", ["Métrica", "Conjunto A", "Conjunto B"], linhas, nota)


if __name__ == "__main__":
    main()
