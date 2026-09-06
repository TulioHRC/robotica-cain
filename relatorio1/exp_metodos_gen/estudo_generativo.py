#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
estudo_generativo.py
====================

Reprodutibilidade da secao de metodos generativos do
Relatorio 1 (Mecanica e fabricacao digital -- caixa planetaria de um estagio
fabricada em FDM).

Uso:
    python3 estudo_generativo.py                 # tudo (mais lento)
    python3 estudo_generativo.py --modulo A
    python3 estudo_generativo.py --modulo B
    python3 estudo_generativo.py --nel 90 --iters 30   # rodada rapida

Saidas (diretorio ./saidas):
    topologia_vf*.png        campos de densidade otimizados
    ot_pareto.png            compliancia normalizada x fracao de volume
    ot_resultados.csv        tabela do Modulo A
    busca_dentes.png         razao x diametro externo (planetaria e Wolfrom)
    busca_planetaria.csv     solucoes viaveis da planetaria simples
    busca_wolfrom.csv        solucoes viaveis do trem de Wolfrom

Dependencias: numpy, scipy, matplotlib.

Referencias de metodo:
    Sigmund (2001), Struct. Multidisc. Optim. 21(2):120-127  -- codigo 99 linhas
    Andreassen et al. (2011), Struct. Multidisc. Optim. 43(1):1-16 -- top88
    Bendsoe & Sigmund (2004), Topology Optimization, Springer
"""

import argparse
import csv
import os
import time

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve
from scipy.ndimage import binary_erosion

SAIDAS = "saidas"


# Projeto de referencia escolhido pelo Modulo B:
#   m = 1,0 mm | z_s = 17 | z_p = 19 | z_r = 55 | k = 3 satelites | i = 4,235
M_REF, ZS_REF, ZP_REF, ZR_REF, K_REF = 1.0, 17, 19, 55, 3
R_PINO = M_REF * (ZS_REF + ZP_REF) / 2.0   # 18,0 mm  distancia entre centros
R_EXT = M_REF * (ZR_REF - 2.0) / 2.0 - 0.5 # 26,0 mm  livre do topo do anel
R_FURO = 5.0        # raio do furo central (eixo de saida)       [mm]
R_BOSS = 3.0        # raio do furo de cada pino de satelite      [mm]
ESP_ANEL = 2.0      # espessura das regioes solidas obrigatorias [mm]
N_PINOS = K_REF     # numero de satelites
TORQUE = 1.5        # torque no porta-satelites [N.m] (carga de referencia)

# Parametros SIMP
PENAL = 3.0         # expoente de penalizacao
E0, EMIN, NU = 1.0, 1e-9, 0.3
D_BICO = 0.4        # diametro do bico da impressora [mm]


# =============================================================================
# MODULO A -- OTIMIZACAO TOPOLOGICA (SIMP / OC)
# =============================================================================
def matriz_elemento(nu=NU):
    """Rigidez do elemento Q4 bilinear, estado plano de tensao, lado unitario."""
    k = np.array([1/2 - nu/6, 1/8 + nu/8, -1/4 - nu/12, -1/8 + 3*nu/8,
                  -1/4 + nu/12, -1/8 - nu/8, nu/6, 1/8 - 3*nu/8])
    KE = 1/(1 - nu**2) * np.array([
        [k[0], k[1], k[2], k[3], k[4], k[5], k[6], k[7]],
        [k[1], k[0], k[7], k[6], k[5], k[4], k[3], k[2]],
        [k[2], k[7], k[0], k[5], k[6], k[3], k[4], k[1]],
        [k[3], k[6], k[5], k[0], k[7], k[2], k[1], k[4]],
        [k[4], k[5], k[6], k[7], k[0], k[1], k[2], k[3]],
        [k[5], k[4], k[3], k[2], k[1], k[0], k[7], k[6]],
        [k[6], k[3], k[4], k[1], k[2], k[7], k[0], k[5]],
        [k[7], k[2], k[1], k[4], k[3], k[6], k[5], k[0]]])
    return KE


def malha(nel):
    """Malha estruturada nel x nel cobrindo o quadrado [-R_EXT, R_EXT]^2."""
    h = 2 * R_EXT / nel                      # tamanho do elemento [mm]
    ix, iy = np.meshgrid(np.arange(nel), np.arange(nel), indexing="ij")
    xc = -R_EXT + (ix + 0.5) * h             # centro dos elementos
    yc = -R_EXT + (iy + 0.5) * h
    return h, xc.ravel(), yc.ravel()


def regioes(nel, xc, yc):
    """Classifica os elementos em vazio fixo, solido fixo e dominio de projeto."""
    r = np.hypot(xc, yc)
    vazio = r > R_EXT
    vazio |= r < R_FURO
    solido = (r >= R_FURO) & (r <= R_FURO + ESP_ANEL)          # cubo
    ang = 2 * np.pi * np.arange(N_PINOS) / N_PINOS
    for a in ang:
        px, py = R_PINO * np.cos(a), R_PINO * np.sin(a)
        d = np.hypot(xc - px, yc - py)
        vazio |= d < R_BOSS
        solido |= (d >= R_BOSS) & (d <= R_BOSS + ESP_ANEL)     # bucha do pino
    solido &= ~vazio
    projeto = ~vazio & ~solido
    return vazio, solido, projeto


def cargas_e_apoios(nel, h):
    """Forcas tangenciais nas buchas dos pinos e engaste no furo do cubo."""
    ndof = 2 * (nel + 1) ** 2
    nx, ny = np.meshgrid(np.arange(nel + 1), np.arange(nel + 1), indexing="ij")
    X = -R_EXT + nx * h
    Y = -R_EXT + ny * h
    R = np.hypot(X, Y)

    # engaste: nos sobre a borda do furo central
    fixos = np.where((R.ravel() >= R_FURO) & (R.ravel() <= R_FURO + 0.6 * ESP_ANEL))[0]
    gl_fixos = np.concatenate([2 * fixos, 2 * fixos + 1])

    # carga: torque distribuido como forca tangencial nas buchas dos pinos
    F = np.zeros(ndof)
    ang = 2 * np.pi * np.arange(N_PINOS) / N_PINOS
    Ft_total = TORQUE * 1000.0 / R_PINO      # [N]  Ft = T/r, T em N.mm
    Ft_pino = Ft_total / N_PINOS
    for a in ang:
        px, py = R_PINO * np.cos(a), R_PINO * np.sin(a)
        d = np.hypot(X - px, Y - py).ravel()
        nos = np.where((d >= R_BOSS) & (d <= R_BOSS + 0.6 * ESP_ANEL))[0]
        if nos.size == 0:
            continue
        # direcao tangencial ao centro do prato, no ponto do no
        rx, ry = X.ravel()[nos], Y.ravel()[nos]
        rr = np.hypot(rx, ry)
        rr[rr == 0] = 1.0
        tx, ty = -ry / rr, rx / rr
        F[2 * nos] += Ft_pino * tx / nos.size
        F[2 * nos + 1] += Ft_pino * ty / nos.size
    return F, gl_fixos


def indices_gl(nel):
    """Mapa elemento -> 8 graus de liberdade (numeracao por colunas)."""
    n1 = np.arange(nel) * (nel + 1)
    e = (n1[:, None] + np.arange(nel)[None, :]).ravel()          # no inferior-esq
    edof = np.stack([2*e, 2*e+1,
                     2*(e+nel+1), 2*(e+nel+1)+1,
                     2*(e+nel+2), 2*(e+nel+2)+1,
                     2*(e+1), 2*(e+1)+1], axis=1)
    return edof


def mapa_simetria(nel, xc, yc, k=N_PINOS):
    """Permutacoes que levam cada elemento aos seus k-1 homologos por rotacao."""
    h = 2 * R_EXT / nel
    mapas = []
    for j in range(1, k):
        a = 2 * np.pi * j / k
        xr = xc * np.cos(a) - yc * np.sin(a)
        yr = xc * np.sin(a) + yc * np.cos(a)
        i = np.clip(((xr + R_EXT) / h - 0.5).round().astype(int), 0, nel - 1)
        jj = np.clip(((yr + R_EXT) / h - 0.5).round().astype(int), 0, nel - 1)
        mapas.append(i * nel + jj)
    return mapas


def simetrizar(v, mapas):
    """Media do campo v sobre a orbita da simetria ciclica de ordem k."""
    acc = v.copy()
    for m in mapas:
        acc = acc + v[m]
    return acc / (len(mapas) + 1)


def matriz_filtro(nel, xc, yc, rmin):
    """Filtro de densidade linear (cone) de raio rmin, em coordenadas fisicas."""
    h = 2 * R_EXT / nel
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
            linhas.append(np.full(m.sum(), e))
            colunas.append(viz[m])
            valores.append(w[m])
    H = coo_matrix((np.concatenate(valores),
                    (np.concatenate(linhas), np.concatenate(colunas))),
                   shape=(nel * nel, nel * nel)).tocsr()
    Hs = np.asarray(H.sum(axis=1)).ravel()
    return H, Hs


def resolver(x, KE, edof, F, livres, ndof):
    """Analise por elementos finitos e compliancia."""
    E = EMIN + x ** PENAL * (E0 - EMIN)
    dados = (KE.ravel()[None, :] * E[:, None]).ravel()
    iK = np.repeat(edof, 8, axis=1).ravel()
    jK = np.tile(edof, (1, 8)).ravel()
    K = coo_matrix((dados, (iK, jK)), shape=(ndof, ndof)).tocsc()
    U = np.zeros(ndof)
    U[livres] = spsolve(K[livres, :][:, livres], F[livres])
    ue = U[edof]
    ce = np.einsum("ij,jk,ik->i", ue, KE, ue)
    c = float(np.sum(E * ce))
    return c, ce


def otimizar(nel, volfrac, iters, rmin, verbose=True, simetria=True):
    """SIMP + filtro de densidade + criterios de otimalidade."""
    h, xc, yc = malha(nel)
    vazio, solido, projeto = regioes(nel, xc, yc)
    KE = matriz_elemento()
    edof = indices_gl(nel)
    ndof = 2 * (nel + 1) ** 2
    F, gl_fixos = cargas_e_apoios(nel, h)
    livres = np.setdiff1d(np.arange(ndof), gl_fixos)
    H, Hs = matriz_filtro(nel, xc, yc, rmin)
    mapas = mapa_simetria(nel, xc, yc) if simetria else []

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
        c, ce = resolver(xf, KE, edof, F, livres, ndof)
        dc = -PENAL * xf ** (PENAL - 1) * (E0 - EMIN) * ce
        dc = np.asarray(H @ (dc / Hs)).ravel()
        dv = np.asarray(H @ (np.ones_like(x) / Hs)).ravel()
        if mapas:                      # impoe simetria ciclica de ordem k
            dc = simetrizar(dc, mapas)

        # criterios de otimalidade restritos ao dominio de projeto
        l1, l2, move = 0.0, 1e9, 0.2
        xp = x[projeto]
        dcp, dvp = dc[projeto], dv[projeto]
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
            print(f"    it {it:3d}  c = {c:11.4f}  vol = {xnovo.mean():.3f} "
                  f"  dx = {mudanca:.4f}")
        if mudanca < 0.005 and it > 15:
            break

    xf = np.asarray(H @ x).ravel() / Hs
    xf[solido] = 1.0
    xf[vazio] = 1e-9
    c, _ = resolver(xf, KE, edof, F, livres, ndof)
    return dict(x=xf, c=c, vazio=vazio, solido=solido, projeto=projeto,
                h=h, hist=hist)


def referencia_solida(nel, rmin):
    """Compliancia e massa do prato macico (dominio de projeto todo cheio)."""
    h, xc, yc = malha(nel)
    vazio, solido, projeto = regioes(nel, xc, yc)
    KE = matriz_elemento()
    edof = indices_gl(nel)
    ndof = 2 * (nel + 1) ** 2
    F, gl_fixos = cargas_e_apoios(nel, h)
    livres = np.setdiff1d(np.arange(ndof), gl_fixos)
    x = np.where(vazio, 1e-9, 1.0)
    c, _ = resolver(x, KE, edof, F, livres, ndof)
    a_el = h * h
    return c, float((~vazio).sum() * a_el), float(projeto.sum() * a_el)


def checar_imprimibilidade(res, corte=0.5):
    nel = int(np.sqrt(res["x"].size))
    h = res["h"]
    solido = (res["x"].reshape(nel, nel) >= corte)
    r = max(1, int(round(D_BICO / h)))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    disco = (xx ** 2 + yy ** 2) <= r ** 2
    erodido = binary_erosion(solido, structure=disco)
    if solido.sum() == 0:
        return 0.0
    return float(erodido.sum()) / float(solido.sum())


def salvar_campo(res, nome, titulo):
    nel = int(np.sqrt(res["x"].size))
    campo = res["x"].reshape(nel, nel).T
    campo = np.where(res["vazio"].reshape(nel, nel).T, np.nan, campo)
    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    ax.imshow(campo, cmap="gray_r", origin="lower", vmin=0, vmax=1,
              extent=[-R_EXT, R_EXT, -R_EXT, R_EXT])
    ax.set_title(titulo, fontsize=9)
    ax.set_xlabel("x [mm]", fontsize=8)
    ax.set_ylabel("y [mm]", fontsize=8)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(SAIDAS, nome), dpi=200)
    plt.close(fig)


def modulo_A(nel, iters, volfracs):
    print("\n=== MODULO A: otimizacao topologica do porta-satelites ===")
    h = 2 * R_EXT / nel
    # escala minima: raio do filtro >= 2 x diametro do bico, e >= 2 elementos
    rmin = max(2.0 * D_BICO, 2.0 * h)
    print(f"  malha {nel}x{nel}  h = {h:.3f} mm   rmin = {rmin:.3f} mm")
    c_sol, area_total, area_proj = referencia_solida(nel, rmin)
    print(f"  prato macico: c = {c_sol:.4f} N.mm   area = {area_total:.1f} mm^2"
          f"   (dominio de projeto = {area_proj:.1f} mm^2,"
          f" {100*area_proj/area_total:.1f}%)")

    linhas = []
    for vf in volfracs:
        print(f"  -> fracao de volume {vf:.2f}")
        t0 = time.time()
        res = otimizar(nel, vf, iters, rmin)
        dt = time.time() - t0
        massa_rel = (area_total - area_proj * (1 - vf)) / area_total
        imprim = checar_imprimibilidade(res)
        np.save(os.path.join(SAIDAS, f"densidade_vf{int(vf*100):02d}.npy"),
                res["x"].reshape(nel, nel))
        linhas.append(dict(volfrac=vf,
                           compliancia=res["c"],
                           compliancia_rel=res["c"] / c_sol,
                           massa_rel=massa_rel,
                           reducao_massa=100 * (1 - massa_rel),
                           imprimibilidade=imprim,
                           tempo_s=dt,
                           iteracoes=len(res["hist"])))
        salvar_campo(res, f"topologia_vf{int(vf*100):02d}.png",
                     f"$f_V$ = {vf:.2f} | $c/c_0$ = {res['c']/c_sol:.2f}")
        print(f"     c = {res['c']:.4f}  c/c0 = {res['c']/c_sol:.3f} "
              f" massa/massa0 = {massa_rel:.3f}  "
              f"imprimibilidade = {imprim:.3f}  ({dt:.1f} s)")

    with open(os.path.join(SAIDAS, "ot_resultados.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)

    fig, ax = plt.subplots(figsize=(5.0, 3.4))
    ax.plot([100*(1-l["massa_rel"]) for l in linhas],
            [l["compliancia_rel"] for l in linhas], "o-")
    ax.axhline(1.0, ls="--", lw=0.8, color="k")
    ax.set_xlabel("reducao de massa do prato [%]")
    ax.set_ylabel(r"compliancia normalizada $c/c_0$")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(SAIDAS, "ot_pareto.png"), dpi=200)
    plt.close(fig)
    return linhas, c_sol, area_total, area_proj


# =============================================================================
# MODULO B -- BUSCA COMBINATORIA SOBRE NUMEROS DE DENTES
# =============================================================================
MODULOS = [0.8, 1.0, 1.25, 1.5]   # modulos imprimiveis em FDM [mm]
D_MAX = 60.0                      # envelope externo maximo [mm]
Z_MIN = 17                        # dentes minimos (sem adendo corrigido, 20 graus)
Z_MAX = 90
FOLGA_SAT = 1.0                   # folga minima entre satelites vizinhos [mm]
PERDA_MALHA = 0.03                # perda por par de engrenamento (estimativa)
ETA_MIN = 0.70                    # eficiencia minima aceitavel para o Wolfrom


def interferencia_ok(m, zs, zp, k):
    """Nao-interferencia entre satelites adjacentes (circulos de cabeca)."""
    a = m * (zs + zp) / 2.0                 # distancia entre centros
    passo = 2.0 * a * np.sin(np.pi / k)     # distancia entre centros de satelites
    return passo >= m * (zp + 2) + FOLGA_SAT


def busca_planetaria():
    """Planetaria simples: anel fixo, sol entrada, porta-satelites saida."""
    sol = []
    for m in MODULOS:
        for zs in range(Z_MIN, Z_MAX + 1):
            for zp in range(Z_MIN, Z_MAX + 1):
                zr = zs + 2 * zp                      # coaxialidade
                if zr > Z_MAX + 40:
                    continue
                d_ext = m * (zr + 2.5)                # diametro externo do anel
                if d_ext > D_MAX:
                    continue
                for k in (3, 4, 5):
                    if (zs + zr) % k:                 # montagem / espacamento
                        continue
                    if not interferencia_ok(m, zs, zp, k):
                        continue
                    i = (zs + zr) / zs                # razao de reducao
                    sol.append(dict(m=m, zs=zs, zp=zp, zr=zr, k=k,
                                    i=i, d_ext=d_ext))
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
                    zr2 = zs + zp1 + zp2              # mesma dist. entre centros
                    d_ext = m * (max(zr1, zr2) + 2.5)
                    if d_ext > D_MAX:
                        continue
                    I2 = zr1 * zp2 / (zp1 * zr2)
                    if abs(1 - I2) < 1e-9:
                        continue
                    i = (1 + zr1 / zs) / (1 - I2)
                    if i <= 0 or i > 5000:
                        continue
                    psi = 1.0 / abs(1.0 - I2)      # fator de recirculacao
                    eta = 1.0 / (1.0 + psi * PERDA_MALHA)
                    for k in (3, 4):
                        if (zs + zr1) % k:
                            continue
                        if not interferencia_ok(m, zs, zp1, k):
                            continue
                        sol.append(dict(m=m, zs=zs, zp1=zp1, zp2=zp2,
                                        zr1=zr1, zr2=zr2, k=k,
                                        i=i, d_ext=d_ext, I2=I2,
                                        psi=psi, eta_est=eta))
    return sol


def modulo_B():
    print("\n=== MODULO B: busca combinatoria sobre numeros de dentes ===")
    pl = busca_planetaria()
    wf = busca_wolfrom()
    print(f"  planetaria simples: {len(pl)} combinacoes viaveis")
    print(f"  Wolfrom (3K):       {len(wf)} combinacoes viaveis")

    if pl:
        pl_ord = sorted(pl, key=lambda d: -d["i"])
        print("  melhores razoes (planetaria simples):")
        for d in pl_ord[:5]:
            print(f"    i = {d['i']:6.3f} | m = {d['m']} | z = "
                  f"({d['zs']},{d['zp']},{d['zr']}) k={d['k']} | "
                  f"D = {d['d_ext']:.1f} mm")
        with open(os.path.join(SAIDAS, "busca_planetaria.csv"), "w",
                  newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(pl[0].keys()))
            w.writeheader()
            w.writerows(pl_ord)

    if wf:
        wf_ord = sorted(wf, key=lambda d: -d["i"])
        print("  melhores razoes (Wolfrom 3K):")
        for d in wf_ord[:5]:
            print(f"    i = {d['i']:8.2f} | m = {d['m']} | z = "
                  f"({d['zs']},{d['zp1']}/{d['zp2']},{d['zr1']}/{d['zr2']}) "
                  f"k={d['k']} | D = {d['d_ext']:.1f} mm | I2 = {d['I2']:.4f}"
                  f" | eta_est = {d['eta_est']:.2f}")
        viaveis = [d for d in wf_ord if d["eta_est"] >= ETA_MIN]
        print(f"  com eta_est >= {ETA_MIN:.2f}: {len(viaveis)} solucoes; "
              f"melhor razao:")
        for d in viaveis[:3]:
            print(f"    i = {d['i']:8.2f} | m = {d['m']} | z = "
                  f"({d['zs']},{d['zp1']}/{d['zp2']},{d['zr1']}/{d['zr2']}) "
                  f"k={d['k']} | D = {d['d_ext']:.1f} mm"
                  f" | eta_est = {d['eta_est']:.2f}")
        with open(os.path.join(SAIDAS, "busca_wolfrom.csv"), "w",
                  newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(wf[0].keys()))
            w.writeheader()
            w.writerows(wf_ord)

    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    ax.scatter([d["d_ext"] for d in pl], [d["i"] for d in pl], s=6,
               alpha=0.35, label="planetaria simples")
    ax.scatter([d["d_ext"] for d in wf], [d["i"] for d in wf], s=6,
               alpha=0.25, label="Wolfrom (3K)")
    ax.set_yscale("log")
    ax.set_xlabel("diametro externo do anel [mm]")
    ax.set_ylabel("razao de reducao $i$")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(os.path.join(SAIDAS, "busca_dentes.png"), dpi=200)
    plt.close(fig)
    return pl, wf


# =============================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--modulo", choices=["A", "B", "AB"], default="AB")
    ap.add_argument("--nel", type=int, default=140,
                    help="elementos por lado da malha (Modulo A)")
    ap.add_argument("--iters", type=int, default=60,
                    help="iteracoes maximas de OT")
    ap.add_argument("--volfracs", type=float, nargs="+",
                    default=[0.20, 0.30, 0.40, 0.50, 0.60])
    args = ap.parse_args()

    os.makedirs(SAIDAS, exist_ok=True)
    np.random.seed(0)
    if "A" in args.modulo:
        modulo_A(args.nel, args.iters, args.volfracs)
    if "B" in args.modulo:
        modulo_B()
    print(f"\nArquivos gerados em ./{SAIDAS}/")


if __name__ == "__main__":
    main()
