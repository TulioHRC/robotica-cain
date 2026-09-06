#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dependencias: numpy, scipy, matplotlib.
"""

import argparse
import csv
import os
import time

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import splu
from scipy.spatial import cKDTree
from scipy.ndimage import binary_erosion

SAIDAS = "saidas"

# =============================================================================
# PARAMETROS GLOBAIS
# =============================================================================
PENAL = 3.0          # expoente de penalizacao SIMP
E0, EMIN, NU = 1.0, 1e-9, 0.3
D_BICO = 0.4         # diametro do bico da impressora [mm]
TORQUE = 1.5         # torque de referencia [N.m]

# ---- Redutor cicloidal de referencia (escolhido pelo Modulo B) --------------
#   N = 20 lobos -> 21 pinos de coroa -> i = 20 ; envelope D = 54 mm
CIC = dict(
    N=20,            # numero de lobos do disco
    R=25.0,          # raio do circulo de pinos da coroa [mm]
    RR=2.0,          # raio dos pinos da coroa [mm]
    EXC=1.0,         # excentricidade [mm]
    R_EXC=7.0,       # raio do furo do excentrico (mancal de entrada) [mm]
    N_SAIDA=6,       # numero de pinos de saida
    R_SAIDA=15.0,    # raio de posicionamento dos pinos de saida [mm]
    RH_SAIDA=3.5,    # raio dos furos de saida ( = r_pino + excentricidade )
    RIM=1.2,         # espessura do aro solido obrigatorio no perfil [mm]
    BOSS=1.6,        # espessura das buchas solidas obrigatorias [mm]
)

# ---- Porta-satelites da planetaria (caso de comparacao) --------------------
#   m = 1,0 mm | z_s = 17 | z_p = 19 | z_r = 55 | k = 3 | i = 4,235
PLA = dict(
    M=1.0, ZS=17, ZP=19, ZR=55, K=3,
    R_FURO=5.0,      # raio do furo central (eixo de saida) [mm]
    R_BOSS=3.0,      # raio do furo de cada pino de satelite [mm]
    BOSS=2.0,        # espessura das regioes solidas obrigatorias [mm]
)
PLA["R_PINO"] = PLA["M"] * (PLA["ZS"] + PLA["ZP"]) / 2.0      # 18,0 mm
PLA["R_EXT"] = PLA["M"] * (PLA["ZR"] - 2.0) / 2.0 - 0.5       # 26,0 mm


# =============================================================================
# GEOMETRIA
# =============================================================================
def perfil_cicloidal(N, R, Rr, E, npts=1440):
    """Perfil epitrocoidal reduzido do disco cicloidal.

    Equacoes classicas do disco de N lobos engrenando com N+1 pinos de raio Rr
    dispostos em circulo de raio R, com excentricidade E.
    """
    t = np.linspace(0.0, 2.0 * np.pi, npts, endpoint=False)
    psi = np.arctan2(np.sin((1 - N) * t),
                     (R / (E * N)) - np.cos((1 - N) * t))
    x = R * np.cos(t) - Rr * np.cos(t + psi) - E * np.cos(N * t)
    y = -R * np.sin(t) + Rr * np.sin(t + psi) + E * np.sin(N * t)
    return np.column_stack([x, y])


def malha(nel, rmax):
    """Malha estruturada nel x nel cobrindo o quadrado [-rmax, rmax]^2."""
    h = 2.0 * rmax / nel
    ix, iy = np.meshgrid(np.arange(nel), np.arange(nel), indexing="ij")
    xc = (-rmax + (ix + 0.5) * h).ravel()
    yc = (-rmax + (iy + 0.5) * h).ravel()
    return h, xc, yc


def nos(nel, rmax):
    h = 2.0 * rmax / nel
    nx, ny = np.meshgrid(np.arange(nel + 1), np.arange(nel + 1), indexing="ij")
    return (-rmax + nx * h).ravel(), (-rmax + ny * h).ravel()


# --------------------------- caso: disco cicloidal ---------------------------
def caso_cicloidal(nel):
    """Regioes, apoios e casos de carga do disco cicloidal."""
    c = CIC
    rmax = c["R"] + c["RR"]
    h, xc, yc = malha(nel, rmax)
    poly = perfil_cicloidal(c["N"], c["R"], c["RR"], c["EXC"])

    dentro = Path(poly).contains_points(np.column_stack([xc, yc]))
    dist_borda, _ = cKDTree(poly).query(np.column_stack([xc, yc]))

    vazio = ~dentro
    solido = dentro & (dist_borda <= c["RIM"])                 # aro do perfil

    # furo do excentrico (entrada) e sua bucha
    r = np.hypot(xc, yc)
    vazio |= r < c["R_EXC"]
    solido |= (r >= c["R_EXC"]) & (r <= c["R_EXC"] + c["BOSS"])

    # furos dos pinos de saida e suas buchas
    ang_s = 2.0 * np.pi * np.arange(c["N_SAIDA"]) / c["N_SAIDA"]
    for a in ang_s:
        px, py = c["R_SAIDA"] * np.cos(a), c["R_SAIDA"] * np.sin(a)
        d = np.hypot(xc - px, yc - py)
        vazio |= d < c["RH_SAIDA"]
        solido |= (d >= c["RH_SAIDA"]) & (d <= c["RH_SAIDA"] + c["BOSS"])
    solido &= ~vazio
    projeto = ~vazio & ~solido

    # ---- apoios: bordas dos furos de saida (reacao do porta-pinos) ---------
    X, Y = nos(nel, rmax)
    fixos = np.zeros(X.size, dtype=bool)
    for a in ang_s:
        px, py = c["R_SAIDA"] * np.cos(a), c["R_SAIDA"] * np.sin(a)
        d = np.hypot(X - px, Y - py)
        fixos |= (d >= c["RH_SAIDA"]) & (d <= c["RH_SAIDA"] + 0.6 * c["BOSS"])
    idx = np.where(fixos)[0]
    gl_fixos = np.concatenate([2 * idx, 2 * idx + 1])

    # ---- cargas: contato dos pinos da coroa, em n_fases posicoes -----------
    # Hipotese simplificadora: apenas os pinos da metade carregada transmitem,
    # com intensidade proporcional a sen(phi); a forca e tomada tangencial ao
    # raio do ponto de contato (braco de alavanca = raio de contato).
    ang_poly = np.arctan2(poly[:, 1], poly[:, 0])
    # so podem receber carga os nos que caem dentro do aro solido do perfil,
    # sob pena de a forca ser aplicada em regiao vazia (modo de corpo rigido)
    dentro_nos = Path(poly).contains_points(np.column_stack([X, Y]))
    dist_nos, _ = cKDTree(poly).query(np.column_stack([X, Y]))
    validos = np.where(dentro_nos & (dist_nos <= 0.9 * c["RIM"]))[0]
    arv_nos = cKDTree(np.column_stack([X[validos], Y[validos]]))
    n_pinos = c["N"] + 1
    phis = 2.0 * np.pi * np.arange(n_pinos) / n_pinos

    def campo_forca(fase=0.0):
        F = np.zeros(2 * (nel + 1) ** 2)
        pesos, pontos = [], []
        for p in phis:
            w = np.sin(p - fase)
            if w <= 1e-3:
                continue
            j = int(np.argmin(np.abs(np.angle(np.exp(1j * (ang_poly - p))))))
            pontos.append(poly[j])
            pesos.append(w)
        pontos, pesos = np.array(pontos), np.array(pesos)
        raios = np.hypot(pontos[:, 0], pontos[:, 1])
        escala = TORQUE * 1000.0 / float(np.sum(pesos * raios))   # momento = T
        for (px, py), w in zip(pontos, pesos):
            loc = arv_nos.query_ball_point([px, py], r=2.0 * h)
            if not loc:
                loc = [int(arv_nos.query([px, py])[1])]
            viz = validos[np.asarray(loc)]
            rr = max(np.hypot(px, py), 1e-9)
            f = escala * w
            F[2 * viz] += f * (-py / rr) / viz.size
            F[2 * viz + 1] += f * (px / rr) / viz.size
        return F

    return dict(nome="cicloidal", rmax=rmax, h=h, xc=xc, yc=yc,
                vazio=vazio, solido=solido, projeto=projeto,
                gl_fixos=gl_fixos, campo_forca=campo_forca,
                simetria=0, poly=poly)


# --------------------------- caso: porta-satelites ---------------------------
def caso_carrier(nel):
    """Regioes, apoios e caso de carga do porta-satelites (comparacao)."""
    p = PLA
    rmax = p["R_EXT"]
    h, xc, yc = malha(nel, rmax)
    r = np.hypot(xc, yc)

    vazio = (r > p["R_EXT"]) | (r < p["R_FURO"])
    solido = (r >= p["R_FURO"]) & (r <= p["R_FURO"] + p["BOSS"])
    ang = 2.0 * np.pi * np.arange(p["K"]) / p["K"]
    for a in ang:
        px, py = p["R_PINO"] * np.cos(a), p["R_PINO"] * np.sin(a)
        d = np.hypot(xc - px, yc - py)
        vazio |= d < p["R_BOSS"]
        solido |= (d >= p["R_BOSS"]) & (d <= p["R_BOSS"] + p["BOSS"])
    solido &= ~vazio
    projeto = ~vazio & ~solido

    X, Y = nos(nel, rmax)
    R = np.hypot(X, Y)
    idx = np.where((R >= p["R_FURO"]) & (R <= p["R_FURO"] + 0.6 * p["BOSS"]))[0]
    gl_fixos = np.concatenate([2 * idx, 2 * idx + 1])

    def campo_forca(fase=0.0):
        F = np.zeros(2 * (nel + 1) ** 2)
        Ft = TORQUE * 1000.0 / p["R_PINO"] / p["K"]
        for a in ang:
            px, py = p["R_PINO"] * np.cos(a), p["R_PINO"] * np.sin(a)
            d = np.hypot(X - px, Y - py)
            n = np.where((d >= p["R_BOSS"])
                         & (d <= p["R_BOSS"] + 0.6 * p["BOSS"]))[0]
            if n.size == 0:
                continue
            rr = np.maximum(np.hypot(X[n], Y[n]), 1e-9)
            F[2 * n] += Ft * (-Y[n] / rr) / n.size
            F[2 * n + 1] += Ft * (X[n] / rr) / n.size
        return F

    return dict(nome="carrier", rmax=rmax, h=h, xc=xc, yc=yc,
                vazio=vazio, solido=solido, projeto=projeto,
                gl_fixos=gl_fixos, campo_forca=campo_forca,
                simetria=p["K"], poly=None)


# =============================================================================
# ELEMENTOS FINITOS
# =============================================================================
def matriz_elemento(nu=NU):
    """Rigidez do elemento Q4 bilinear, estado plano de tensao, lado unitario."""
    k = np.array([1/2 - nu/6, 1/8 + nu/8, -1/4 - nu/12, -1/8 + 3*nu/8,
                  -1/4 + nu/12, -1/8 - nu/8, nu/6, 1/8 - 3*nu/8])
    return 1/(1 - nu**2) * np.array([
        [k[0], k[1], k[2], k[3], k[4], k[5], k[6], k[7]],
        [k[1], k[0], k[7], k[6], k[5], k[4], k[3], k[2]],
        [k[2], k[7], k[0], k[5], k[6], k[3], k[4], k[1]],
        [k[3], k[6], k[5], k[0], k[7], k[2], k[1], k[4]],
        [k[4], k[5], k[6], k[7], k[0], k[1], k[2], k[3]],
        [k[5], k[4], k[3], k[2], k[1], k[0], k[7], k[6]],
        [k[6], k[3], k[4], k[1], k[2], k[7], k[0], k[5]],
        [k[7], k[2], k[1], k[4], k[3], k[6], k[5], k[0]]])


def indices_gl(nel):
    """Mapa elemento -> 8 graus de liberdade (numeracao por colunas)."""
    n1 = np.arange(nel) * (nel + 1)
    e = (n1[:, None] + np.arange(nel)[None, :]).ravel()
    return np.stack([2*e, 2*e+1,
                     2*(e+nel+1), 2*(e+nel+1)+1,
                     2*(e+nel+2), 2*(e+nel+2)+1,
                     2*(e+1), 2*(e+1)+1], axis=1)


def resolver_multicaso(x, KE, edof, Fs, livres, ndof):
    """Fatoracao unica da rigidez e solucao para varios casos de carga.

    Retorna a compliancia total (soma sobre os casos) e a energia de deformacao
    por elemento acumulada, usada nas sensibilidades.
    """
    E = EMIN + x ** PENAL * (E0 - EMIN)
    dados = (KE.ravel()[None, :] * E[:, None]).ravel()
    iK = np.repeat(edof, 8, axis=1).ravel()
    jK = np.tile(edof, (1, 8)).ravel()
    K = coo_matrix((dados, (iK, jK)), shape=(ndof, ndof)).tocsc()
    lu = splu(K[livres, :][:, livres].tocsc())

    c_total, ce_total = 0.0, np.zeros(x.size)
    for F in Fs:
        U = np.zeros(ndof)
        U[livres] = lu.solve(F[livres])
        ue = U[edof]
        ce = np.einsum("ij,jk,ik->i", ue, KE, ue)
        ce_total += ce
        c_total += float(np.sum(E * ce))
    return c_total, ce_total


# =============================================================================
# FILTRO E SIMETRIA
# =============================================================================
def matriz_filtro(nel, xc, yc, rmin, h):
    """Filtro de densidade linear (cone) de raio rmin, em coordenadas fisicas."""
    raio_el = int(np.ceil(rmin / h))
    idx = np.arange(nel * nel).reshape(nel, nel)
    linhas, colunas, valores = [], [], []
    for i in range(nel):
        i0, i1 = max(0, i - raio_el), min(nel, i + raio_el + 1)
        for j in range(nel):
            j0, j1 = max(0, j - raio_el), min(nel, j + raio_el + 1)
            viz = idx[i0:i1, j0:j1].ravel()
            e = idx[i, j]
            d = np.hypot(xc[viz] - xc[e], yc[viz] - yc[e])
            w = np.maximum(0.0, rmin - d)
            m = w > 0
            linhas.append(np.full(int(m.sum()), e))
            colunas.append(viz[m])
            valores.append(w[m])
    H = coo_matrix((np.concatenate(valores),
                    (np.concatenate(linhas), np.concatenate(colunas))),
                   shape=(nel * nel, nel * nel)).tocsr()
    return H, np.asarray(H.sum(axis=1)).ravel()


def mapa_simetria(nel, xc, yc, rmax, k):
    """Permutacoes que levam cada elemento aos seus k-1 homologos por rotacao."""
    h = 2.0 * rmax / nel
    mapas = []
    for j in range(1, k):
        a = 2.0 * np.pi * j / k
        xr = xc * np.cos(a) - yc * np.sin(a)
        yr = xc * np.sin(a) + yc * np.cos(a)
        i = np.clip(((xr + rmax) / h - 0.5).round().astype(int), 0, nel - 1)
        jj = np.clip(((yr + rmax) / h - 0.5).round().astype(int), 0, nel - 1)
        mapas.append(i * nel + jj)
    return mapas


def simetrizar(v, mapas):
    acc = v.copy()
    for m in mapas:
        acc = acc + v[m]
    return acc / (len(mapas) + 1)


# =============================================================================
# MODULO A -- OTIMIZACAO TOPOLOGICA
# =============================================================================
def otimizar(caso, nel, volfrac, iters, rmin, n_fases, verbose=True):
    """SIMP + filtro de densidade + criterios de otimalidade, multicaso."""
    xc, yc, h = caso["xc"], caso["yc"], caso["h"]
    vazio, solido, projeto = caso["vazio"], caso["solido"], caso["projeto"]
    KE = matriz_elemento()
    edof = indices_gl(nel)
    ndof = 2 * (nel + 1) ** 2
    livres = np.setdiff1d(np.arange(ndof), caso["gl_fixos"])
    H, Hs = matriz_filtro(nel, xc, yc, rmin, h)
    mapas = (mapa_simetria(nel, xc, yc, caso["rmax"], caso["simetria"])
             if caso["simetria"] else [])
    nf = max(n_fases, 1)
    Fs = [caso["campo_forca"](2.0 * np.pi * j / nf) for j in range(nf)]

    n_proj = int(projeto.sum())
    x = np.zeros(nel * nel)
    x[solido] = 1.0
    x[projeto] = volfrac
    x[vazio] = 1e-9

    hist = []
    for it in range(iters):
        xf = np.asarray(H @ x).ravel() / Hs
        xf[solido] = 1.0
        xf[vazio] = 1e-9
        c, ce = resolver_multicaso(xf, KE, edof, Fs, livres, ndof)
        dc = -PENAL * xf ** (PENAL - 1) * (E0 - EMIN) * ce
        dc = np.asarray(H @ (dc / Hs)).ravel()
        dv = np.asarray(H @ (np.ones_like(x) / Hs)).ravel()
        if mapas:
            dc = simetrizar(dc, mapas)

        l1, l2, move = 0.0, 1e9, 0.2
        xp, dcp, dvp = x[projeto], dc[projeto], dv[projeto]
        while (l2 - l1) / max(l1 + l2, 1e-12) > 1e-4:
            lmid = 0.5 * (l1 + l2)
            xnovo = np.clip(np.clip(xp * np.sqrt(np.maximum(-dcp, 1e-12)
                                                 / (lmid * dvp)),
                                    xp - move, xp + move), 1e-3, 1.0)
            if xnovo.sum() > volfrac * n_proj:
                l1 = lmid
            else:
                l2 = lmid
        mudanca = float(np.max(np.abs(xnovo - xp)))
        x[projeto] = xnovo
        hist.append(c)
        if verbose and (it % 10 == 0 or it == iters - 1):
            print(f"    it {it:3d}  c = {c:11.4f}  vol = {xnovo.mean():.3f}"
                  f"  dx = {mudanca:.4f}")
        if mudanca < 0.005 and it > 15:
            break

    xf = np.asarray(H @ x).ravel() / Hs
    xf[solido] = 1.0
    xf[vazio] = 1e-9
    c, _ = resolver_multicaso(xf, KE, edof, Fs, livres, ndof)
    return dict(x=xf, c=c, hist=hist)


def referencia_solida(caso, nel, n_fases):
    """Compliancia e areas da peca macica (dominio de projeto todo cheio)."""
    KE = matriz_elemento()
    edof = indices_gl(nel)
    ndof = 2 * (nel + 1) ** 2
    livres = np.setdiff1d(np.arange(ndof), caso["gl_fixos"])
    nf = max(n_fases, 1)
    Fs = [caso["campo_forca"](2.0 * np.pi * j / nf) for j in range(nf)]
    x = np.where(caso["vazio"], 1e-9, 1.0)
    c, _ = resolver_multicaso(x, KE, edof, Fs, livres, ndof)
    a = caso["h"] ** 2
    return c, float((~caso["vazio"]).sum() * a), float(caso["projeto"].sum() * a)


def checar_imprimibilidade(x, nel, h, corte=0.5):
    """Fracao da area solida que sobrevive a uma erosao de raio d_bico.

    Membros mais estreitos que 2*d_bico (uma ida e volta do bico) desaparecem
    sob a erosao: o indicador mede quanto do resultado da OT e diretamente
    depositavel sem afinar paredes.
    """
    solido = (x.reshape(nel, nel) >= corte)
    if solido.sum() == 0:
        return 0.0
    r = max(1, int(round(D_BICO / h)))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    disco = (xx ** 2 + yy ** 2) <= r ** 2
    return float(binary_erosion(solido, structure=disco).sum()) / float(solido.sum())


def salvar_campo(x, caso, nel, nome, titulo):
    campo = np.where(caso["vazio"].reshape(nel, nel).T, np.nan,
                     x.reshape(nel, nel).T)
    rmax = caso["rmax"]
    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    ax.imshow(campo, cmap="gray_r", origin="lower", vmin=0, vmax=1,
              extent=[-rmax, rmax, -rmax, rmax])
    if caso["poly"] is not None:
        p = np.vstack([caso["poly"], caso["poly"][:1]])
        ax.plot(p[:, 0], p[:, 1], lw=0.6, color="0.45")
    ax.set_title(titulo, fontsize=9)
    ax.set_xlabel("x [mm]", fontsize=8)
    ax.set_ylabel("y [mm]", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(os.path.join(SAIDAS, nome), dpi=200)
    plt.close(fig)


def salvar_dominio(caso, nel):
    """Figura de conferencia: vazio, solido obrigatorio e dominio de projeto."""
    m = np.zeros(nel * nel)
    m[caso["projeto"]] = 1.0
    m[caso["solido"]] = 2.0
    m = np.where(caso["vazio"], np.nan, m).reshape(nel, nel).T
    rmax = caso["rmax"]
    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    ax.imshow(m, cmap="viridis", origin="lower", vmin=0, vmax=2,
              extent=[-rmax, rmax, -rmax, rmax])
    ax.set_title(f"dominio: {caso['nome']} (claro = solido obrigatorio)",
                 fontsize=8)
    ax.set_aspect("equal")
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(SAIDAS, f"dominio_{caso['nome']}.png"), dpi=200)
    plt.close(fig)


def modulo_A(peca, nel, iters, volfracs, n_fases):
    print(f"\n=== MODULO A: otimizacao topologica -- peca: {peca} ===")
    caso = caso_cicloidal(nel) if peca == "cicloidal" else caso_carrier(nel)
    h = caso["h"]
    rmin = max(2.0 * D_BICO, 2.0 * h)
    nf = n_fases if peca == "cicloidal" else 1
    print(f"  malha {nel}x{nel}  h = {h:.3f} mm  rmin = {rmin:.3f} mm"
          f"  fases de carga = {nf}")
    salvar_dominio(caso, nel)

    c_sol, area_total, area_proj = referencia_solida(caso, nel, nf)
    print(f"  peca macica: c0 = {c_sol:.4f} N.mm   area = {area_total:.1f} mm^2"
          f"   (dominio de projeto = {area_proj:.1f} mm^2,"
          f" {100*area_proj/area_total:.1f}%)")

    linhas = []
    for vf in volfracs:
        print(f"  -> fracao de volume {vf:.2f}")
        t0 = time.time()
        res = otimizar(caso, nel, vf, iters, rmin, nf)
        dt = time.time() - t0
        massa_rel = (area_total - area_proj * (1 - vf)) / area_total
        imprim = checar_imprimibilidade(res["x"], nel, h)
        np.save(os.path.join(SAIDAS,
                             f"densidade_{peca}_vf{int(vf*100):02d}.npy"),
                res["x"].reshape(nel, nel))
        linhas.append(dict(peca=peca, volfrac=vf, compliancia=res["c"],
                           compliancia_rel=res["c"] / c_sol,
                           massa_rel=massa_rel,
                           reducao_massa=100 * (1 - massa_rel),
                           imprimibilidade=imprim,
                           iteracoes=len(res["hist"]), tempo_s=dt))
        salvar_campo(res["x"], caso, nel,
                     f"topologia_{peca}_vf{int(vf*100):02d}.png",
                     f"$f_V$ = {vf:.2f} | $c/c_0$ = {res['c']/c_sol:.2f}")
        print(f"     c/c0 = {res['c']/c_sol:.3f}  massa/massa0 = {massa_rel:.3f}"
              f"  imprimibilidade = {imprim:.3f}  ({dt:.1f} s)")

    with open(os.path.join(SAIDAS, f"ot_resultados_{peca}.csv"), "w",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)

    fig, ax = plt.subplots(figsize=(5.0, 3.4))
    ax.plot([l["reducao_massa"] for l in linhas],
            [l["compliancia_rel"] for l in linhas], "o-")
    ax.axhline(1.0, ls="--", lw=0.8, color="k")
    ax.set_xlabel("reducao de massa da peca [%]")
    ax.set_ylabel(r"compliancia normalizada $c/c_0$")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(SAIDAS, f"ot_pareto_{peca}.png"), dpi=200)
    plt.close(fig)
    return linhas


# =============================================================================
# MODULO B -- BUSCA COMBINATORIA SOBRE ARQUITETURAS
# =============================================================================
MODULOS = [0.8, 1.0, 1.25, 1.5]   # modulos imprimiveis em FDM [mm]
D_MAX = 60.0                      # envelope externo maximo [mm]
Z_MIN, Z_MAX = 17, 90             # dentes minimos (20 graus) e maximos
FOLGA = 1.0                       # folga minima [mm]
PERDA_MALHA = 0.03                # perda por par de engrenamento (estimativa)
ETA_MIN = 0.70                    # rendimento minimo aceitavel
RR_LISTA = [1.5, 2.0, 2.5, 3.0]   # raios de pino de coroa imprimiveis [mm]
EXC_LISTA = [0.5, 0.75, 1.0, 1.25, 1.5]
K1_MAX = 0.8                      # razao cicloidal maxima (sem rebaixo)


def interferencia_ok(m, zs, zp, k):
    a = m * (zs + zp) / 2.0
    return 2.0 * a * np.sin(np.pi / k) >= m * (zp + 2) + FOLGA


def busca_planetaria():
    """Planetaria simples: anel fixo, sol entrada, porta-satelites saida."""
    sol = []
    for m in MODULOS:
        for zs in range(Z_MIN, Z_MAX + 1):
            for zp in range(Z_MIN, Z_MAX + 1):
                zr = zs + 2 * zp
                if m * (zr + 2.5) > D_MAX:
                    continue
                for k in (3, 4, 5):
                    if (zs + zr) % k or not interferencia_ok(m, zs, zp, k):
                        continue
                    sol.append(dict(m=m, zs=zs, zp=zp, zr=zr, k=k,
                                    i=(zs + zr) / zs, d_ext=m * (zr + 2.5)))
    return sol


def busca_wolfrom():
    """Trem composto de Wolfrom (3K): sol, satelite composto, dois aneis."""
    sol = []
    for m in MODULOS:
        for zs in range(Z_MIN, 61):
            for zp1 in range(Z_MIN, 61):
                zr1 = zs + 2 * zp1
                for zp2 in range(Z_MIN, 61):
                    if zp2 == zp1:
                        continue
                    zr2 = zs + zp1 + zp2
                    d_ext = m * (max(zr1, zr2) + 2.5)
                    if d_ext > D_MAX:
                        continue
                    I2 = zr1 * zp2 / (zp1 * zr2)
                    if abs(1 - I2) < 1e-9:
                        continue
                    i = (1 + zr1 / zs) / (1 - I2)
                    if i <= 0 or i > 5000:
                        continue
                    psi = 1.0 / abs(1.0 - I2)
                    eta = 1.0 / (1.0 + psi * PERDA_MALHA)
                    for k in (3, 4):
                        if (zs + zr1) % k or not interferencia_ok(m, zs, zp1, k):
                            continue
                        sol.append(dict(m=m, zs=zs, zp1=zp1, zp2=zp2, zr1=zr1,
                                        zr2=zr2, k=k, i=i, d_ext=d_ext, I2=I2,
                                        psi=psi, eta_est=eta))
    return sol


def busca_cicloidal():
    """Redutor cicloidal de um estagio: i = N (numero de lobos)."""
    sol = []
    for N in range(8, 61):
        for R in np.arange(12.0, 29.01, 0.5):
            for Rr in RR_LISTA:
                d_ext = 2.0 * (R + Rr)
                if d_ext > D_MAX:
                    continue
                # passo entre pinos da coroa: precisa caber o pino mais folga
                if 2.0 * np.pi * R / (N + 1) < 2.0 * Rr + FOLGA:
                    continue
                for E in EXC_LISTA:
                    k1 = E * N / R                  # razao cicloidal
                    if k1 > K1_MAX:
                        continue
                    sol.append(dict(N=N, R=float(R), Rr=Rr, E=E, k1=k1,
                                    i=float(N), d_ext=d_ext))
    return sol


def _salvar(nome, dados):
    if not dados:
        return
    with open(os.path.join(SAIDAS, nome), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dados[0].keys()))
        w.writeheader()
        w.writerows(dados)


def modulo_B():
    print("\n=== MODULO B: busca combinatoria sobre arquiteturas ===")
    pl = sorted(busca_planetaria(), key=lambda d: -d["i"])
    wf = sorted(busca_wolfrom(), key=lambda d: -d["i"])
    ci = sorted(busca_cicloidal(), key=lambda d: -d["i"])

    print(f"  planetaria simples: {len(pl)} solucoes | i_max = {pl[0]['i']:.3f}"
          f"  ({pl[0]['zs']}/{pl[0]['zp']}/{pl[0]['zr']}, m={pl[0]['m']},"
          f" k={pl[0]['k']}, D={pl[0]['d_ext']:.1f} mm)")
    print(f"  Wolfrom (3K):       {len(wf)} solucoes | i_max = {wf[0]['i']:.1f}"
          f"  (eta_est = {wf[0]['eta_est']:.2f}, D={wf[0]['d_ext']:.1f} mm)")
    viav = [d for d in wf if d["eta_est"] >= ETA_MIN]
    if viav:
        print(f"    com eta_est >= {ETA_MIN:.2f}: {len(viav)} solucoes |"
              f" i_max = {viav[0]['i']:.1f}"
              f"  ({viav[0]['zs']}; {viav[0]['zp1']}/{viav[0]['zp2']};"
              f" {viav[0]['zr1']}/{viav[0]['zr2']}, D={viav[0]['d_ext']:.1f} mm)")
    print(f"  cicloidal:          {len(ci)} solucoes | i_max = {ci[0]['i']:.0f}"
          f"  (N={ci[0]['N']}, R={ci[0]['R']:.1f}, Rr={ci[0]['Rr']},"
          f" E={ci[0]['E']}, k1={ci[0]['k1']:.2f}, D={ci[0]['d_ext']:.1f} mm)")
    sub = [d for d in ci if d["d_ext"] <= 57.5]
    if sub:
        print(f"    com D <= 57,5 mm (envelope da caixa de referencia):"
              f" i_max = {sub[0]['i']:.0f}  (N={sub[0]['N']},"
              f" R={sub[0]['R']:.1f}, Rr={sub[0]['Rr']}, E={sub[0]['E']},"
              f" D={sub[0]['d_ext']:.1f} mm)")

    _salvar("busca_planetaria.csv", pl)
    _salvar("busca_wolfrom.csv", wf)
    _salvar("busca_cicloidal.csv", ci)

    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    ax.scatter([d["d_ext"] for d in pl], [d["i"] for d in pl], s=6, alpha=0.35,
               label="planetaria simples")
    ax.scatter([d["d_ext"] for d in ci], [d["i"] for d in ci], s=6, alpha=0.30,
               label="cicloidal")
    ax.scatter([d["d_ext"] for d in wf], [d["i"] for d in wf], s=6, alpha=0.18,
               label="Wolfrom (3K)")
    if viav:
        ax.scatter([d["d_ext"] for d in viav], [d["i"] for d in viav], s=6,
                   alpha=0.55, label=r"Wolfrom, $\eta \geq 0{,}70$")
    ax.set_yscale("log")
    ax.set_xlabel("diametro externo [mm]")
    ax.set_ylabel("razao de reducao $i$")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(os.path.join(SAIDAS, "busca_arquiteturas.png"), dpi=200)
    plt.close(fig)
    return pl, wf, ci


# =============================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--modulo", choices=["A", "B", "AB"], default="AB")
    ap.add_argument("--peca", choices=["cicloidal", "carrier"],
                    default="cicloidal", help="peca alvo do Modulo A")
    ap.add_argument("--nel", type=int, default=140)
    ap.add_argument("--iters", type=int, default=60)
    ap.add_argument("--fases", type=int, default=6,
                    help="posicoes angulares do campo de contato (cicloidal)")
    ap.add_argument("--volfracs", type=float, nargs="+",
                    default=[0.20, 0.30, 0.40, 0.50, 0.60])
    args = ap.parse_args()

    os.makedirs(SAIDAS, exist_ok=True)
    np.random.seed(0)
    if "A" in args.modulo:
        modulo_A(args.peca, args.nel, args.iters, args.volfracs, args.fases)
    if "B" in args.modulo:
        modulo_B()
    print(f"\nArquivos gerados em ./{SAIDAS}/")


if __name__ == "__main__":
    main()