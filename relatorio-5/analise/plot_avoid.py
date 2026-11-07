import argparse
import math
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from comum import (AZUL, DOURADO, MM, RAIZ, VERMELHO, arena, arquivos, distancia, formatador,
                   media, salvar, tabela_latex)

LIMIAR = 0.045
DURACAO = 300.0


def colisoes(d):
    abaixo = d < LIMIAR
    inicio = abaixo & ~np.r_[False, abaixo[:-1]]
    return np.flatnonzero(inicio)


def cobertura(df, celula=0.1):
    n = int(round(2 / celula))
    i = np.clip(((df["x"] + 1) / celula).astype(int), 0, n - 1)
    j = np.clip(((df["y"] + 1) / celula).astype(int), 0, n - 1)
    visitadas = set(zip(i, j))
    livres = 0
    for a in range(n):
        for b in range(n):
            cx, cy = -1 + celula * (a + 0.5), -1 + celula * (b + 0.5)
            if math.hypot(cx, cy) > 0.15 + 0.037 and max(abs(cx), abs(cy)) < 1 - 0.037:
                livres += 1
    return 100.0 * len(visitadas) / livres


def metricas(df):
    d = df["d_min"].to_numpy()
    T = df["t"].iloc[-1] - df["t"].iloc[0]
    L = distancia(df)
    return {
        "L": L,
        "vel": L / T,
        "col": len(colisoes(d)),
        "pct": 100.0 * np.mean(d < LIMIAR),
        "dmin": d.min(),
        "dmed": d.mean(),
        "cob": cobertura(df),
    }


def trajetoria(df, saida, nome, largura):
    fig, ax = plt.subplots(figsize=(largura * MM, largura * 0.9 * MM))
    arena(ax, True)
    ax.plot(df["x"], df["y"], color=AZUL, lw=0.5, alpha=0.85)
    ax.plot(df["x"].iloc[0], df["y"].iloc[0], "o", color=DOURADO, ms=5, mec="k", mew=0.4, label="partida")
    idx = colisoes(df["d_min"].to_numpy())
    if len(idx):
        ax.plot(df["x"].iloc[idx], df["y"].iloc[idx], "x", color=VERMELHO, ms=5, mew=1.2,
                label="colisão (%d)" % len(idx))
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, frameon=False)
    salvar(fig, saida, nome)


def dmin_tempo(df, saida):
    fig, ax = plt.subplots(figsize=(165 * MM, 50 * MM))
    ax.plot(df["t"], df["d_min"], color=AZUL, lw=0.6)
    ax.axhline(LIMIAR, color=VERMELHO, ls="--", lw=0.9, label="limiar de colisão (0,045 m)")
    for i in colisoes(df["d_min"].to_numpy()):
        ax.axvline(df["t"].iloc[i], color=VERMELHO, lw=0.6, alpha=0.5)
    ax.set_xlim(0, df["t"].iloc[-1])
    ax.set_ylim(0, 0.52)
    ax.set_xlabel("t (s)")
    ax.set_ylabel("$d_{\\min}$ (m)")
    ax.yaxis.set_major_formatter(formatador(2))
    ax.legend(loc="lower right", framealpha=0.9)
    salvar(fig, saida, "avoid_dmin_A.pdf")


def histograma(dfa, dfb, saida):
    fig, ax = plt.subplots(figsize=(85 * MM, 76 * MM))
    bins = np.linspace(0.0, 0.5, 51)
    ax.hist(dfa["d_min"], bins=bins, density=True, color=AZUL, alpha=0.55, label="A")
    ax.hist(dfb["d_min"], bins=bins, density=True, color=DOURADO, alpha=0.55, label="B")
    ax.axvline(LIMIAR, color=VERMELHO, ls="--", lw=0.9, label="limiar")
    ax.set_xlabel("$d_{\\min}$ (m)")
    ax.set_ylabel("densidade")
    ax.xaxis.set_major_formatter(formatador(1))
    ax.yaxis.set_major_formatter(formatador(0))
    ax.legend(framealpha=0.9)
    salvar(fig, saida, "avoid_dmin_AB.pdf")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--a", nargs="*")
    p.add_argument("--b", nargs="*")
    p.add_argument("--sem-vies", nargs="*")
    p.add_argument("--saida", default=os.path.join(RAIZ, "relatorio"))
    args = p.parse_args()
    fa = arquivos("exercicios/avoid/logs/avoid_A_*.csv", args.a, DURACAO)
    fb = arquivos("exercicios/avoid/logs/avoid_B_*.csv", args.b, DURACAO)
    if not fa or not fb:
        raise SystemExit("faltam ensaios completos de A ou de B")
    da = [pd.read_csv(f) for f in fa]
    db = [pd.read_csv(f) for f in fb]
    ma = [metricas(d) for d in da]
    mb = [metricas(d) for d in db]
    for nome, fs, ms in (("A", fa, ma), ("B", fb, mb)):
        for f, m in zip(fs, ms):
            print(nome, os.path.relpath(f, RAIZ), {k: round(v, 4) for k, v in m.items()})
    trajetoria(da[-1], args.saida, "avoid_trajetoria_A.pdf", 89)
    trajetoria(db[-1], args.saida, "avoid_trajetoria_B.pdf", 85)
    dmin_tempo(da[-1], args.saida)
    histograma(pd.concat(da), pd.concat(db), args.saida)
    fv = arquivos("exercicios/avoid/logs_sem_vies/*.csv", args.sem_vies, DURACAO)
    if not args.sem_vies:
        fv += arquivos("exercicios/avoid/logs/avoid_SV_*.csv", None, DURACAO)
    fv = sorted(fv, key=os.path.basename)
    if fv:
        dv = pd.read_csv(fv[-1])
        print("sem viés", os.path.relpath(fv[-1], RAIZ), {k: round(v, 4) for k, v in metricas(dv).items()})
        trajetoria(dv, args.saida, "avoid_trajetoria_sem_vies.pdf", 85)
    campos = [
        ("Distância percorrida $L$ (\\unit{\\metre})", "L", 1),
        ("Velocidade média $L/T$ (\\unit{\\metre\\per\\second})", "vel", 3),
        ("Número de colisões $N_{\\text{col}}$", "col", 1 if len(ma) > 1 or len(mb) > 1 else 0),
        ("Tempo com $d_{\\min} < \\qty{0.045}{\\metre}$ (\\unit{\\percent})", "pct", 2),
        ("Menor $d_{\\min}$ (\\unit{\\metre})", "dmin", 3),
        ("$d_{\\min}$ médio (\\unit{\\metre})", "dmed", 3),
        ("Cobertura da arena (\\unit{\\percent})", "cob", 1),
    ]
    linhas = [[r, media([m[k] for m in ma], c), media([m[k] for m in mb], c)] for r, k, c in campos]
    nota = ""
    if len(ma) > 1 or len(mb) > 1:
        nota = "Média $\\pm$ desvio padrão de %d ensaios (A) e %d ensaios (B)." % (len(ma), len(mb))
    tabela_latex(args.saida, "tab_avoid_metricas.tex",
                 "Métricas dos ensaios de \\qty{300}{\\second} do nó \\texttt{avoid}.",
                 "tab:avoid-metricas", ["Métrica", "Config.\\ A", "Config.\\ B"], linhas, nota)


if __name__ == "__main__":
    main()
