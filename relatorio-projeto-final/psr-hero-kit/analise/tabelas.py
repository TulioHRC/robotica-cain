import argparse
import csv
import glob
import json
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOGOS = ("sumo", "ctf", "soccer")
ORDEM = {"parado": 0, "anterior": 1}
LADOS = {"sumo": ("\\cod{hero_0}", "\\cod{hero_1}"), "ctf": ("azul", "vermelho"),
         "soccer": ("azul", "vermelho")}


def papel(nome, jogo):
    if nome == "none":
        return "parado"
    if nome == jogo:
        return "final"
    if nome == jogo + "_v1":
        return "anterior"
    return nome


def ler(caminho):
    m = re.match(r"(sumo|ctf|soccer)_(.+)_x_(.+)_\d{8}-\d{6}\.csv$", os.path.basename(caminho))
    if not m:
        return None
    jogo, time0, time1 = m.groups()
    with open(caminho) as f:
        linhas = [(float(r["t"]), json.loads(r["estado"])) for r in csv.DictReader(f)]
    if len(linhas) < 2:
        return None
    return jogo, papel(time0, jogo), papel(time1, jogo), linhas


def sumo(linhas, lado):
    ini, fim = linhas[0][1], linhas[-1][1]
    v = fim["wins"][lado] - ini["wins"][lado]
    d = fim["wins"][1 - lado] - ini["wins"][1 - lado]
    e = fim["draws"] - ini["draws"]
    tempos = []
    for (_, a), (_, b) in zip(linhas, linhas[1:]):
        if b["wins"][lado] > a["wins"][lado]:
            tempos.append(a["round_time"])
    return {"v": v, "d": d, "e": e, "tempos": tempos}


def ctf(linhas, lado):
    ini, fim = linhas[0][1], linhas[-1][1]
    pro = fim["score"][lado] - ini["score"][lado]
    contra = fim["score"][1 - lado] - ini["score"][1 - lado]
    n = len(fim["tags"])
    meus = range(0, n // 2) if lado == 0 else range(n // 2, n)
    deles = range(n // 2, n) if lado == 0 else range(0, n // 2)
    sofridas = sum(fim["tags"][i] - ini["tags"][i] for i in meus)
    feitas = sum(fim["tags"][i] - ini["tags"][i] for i in deles)
    return {"pro": pro, "contra": contra, "feitas": feitas, "sofridas": sofridas}


def soccer(linhas, lado):
    ini, fim = linhas[0][1], linhas[-1][1]
    times = ("blue", "red")
    pro = fim[times[lado]] - ini[times[lado]]
    contra = fim[times[1 - lado]] - ini[times[1 - lado]]
    return {"pro": pro, "contra": contra}


def resultado(r):
    return "v" if r["pro"] > r["contra"] else ("d" if r["pro"] < r["contra"] else "e")


def completa(jogo, linhas, duracao, rodadas):
    ini, fim = linhas[0][1], linhas[-1][1]
    if jogo == "sumo":
        return sum(fim["wins"]) + fim["draws"] - sum(ini["wins"]) - ini["draws"] >= rodadas
    return linhas[-1][0] >= 0.98 * duracao


def agrupar(arquivos, duracao, rodadas):
    grupos = {}
    for caminho in arquivos:
        dados = ler(caminho)
        if dados is None:
            print("ignorado:", os.path.relpath(caminho, RAIZ))
            continue
        jogo, p0, p1, linhas = dados
        if not completa(jogo, linhas, duracao, rodadas):
            print("ignorado (partida incompleta):", os.path.relpath(caminho, RAIZ))
            continue
        if p0 == "final" and p1 != "final":
            lado, adv = 0, p1
        elif p1 == "final" and p0 != "final":
            lado, adv = 1, p0
        else:
            print("ignorado (sem versão final de um lado só):", os.path.relpath(caminho, RAIZ))
            continue
        r = {"sumo": sumo, "ctf": ctf, "soccer": soccer}[jogo](linhas, lado)
        print(jogo, adv, "lado", lado, {k: v for k, v in r.items() if k != "tempos"},
              os.path.relpath(caminho, RAIZ))
        grupos.setdefault(jogo, {}).setdefault((adv, lado), []).append(r)
    return grupos


def num(x, casas=1):
    return ("%.*f" % (casas, x)).replace(".", ",")


def linhas_sumo(grupo):
    saida = []
    for (adv, lado), rs in grupo:
        tempos = [t for r in rs for t in r["tempos"]]
        media = num(sum(tempos) / len(tempos)) if tempos else "--"
        saida.append([adv, LADOS["sumo"][lado], str(sum(r["v"] for r in rs)),
                      str(sum(r["d"] for r in rs)), str(sum(r["e"] for r in rs)), media])
    return saida


def linhas_ctf(grupo):
    saida = []
    for (adv, lado), rs in grupo:
        ved = [resultado(r) for r in rs]
        saida.append([adv, LADOS["ctf"][lado], str(sum(r["pro"] for r in rs)),
                      str(sum(r["contra"] for r in rs)), str(sum(r["feitas"] for r in rs)),
                      str(sum(r["sofridas"] for r in rs)),
                      "%d / %d / %d" % (ved.count("v"), ved.count("e"), ved.count("d"))])
    return saida


def linhas_soccer(grupo):
    saida = []
    for (adv, lado), rs in grupo:
        pro = sum(r["pro"] for r in rs)
        contra = sum(r["contra"] for r in rs)
        ved = [resultado(r) for r in rs]
        saida.append([adv, LADOS["soccer"][lado], str(pro), str(contra), "%+d" % (pro - contra),
                      "%d / %d / %d" % (ved.count("v"), ved.count("e"), ved.count("d"))])
    return saida


TABELAS = {
    "sumo": ("Resultados do sumô, do ponto de vista da versão final. Soma das rodadas de cada condição.",
             "tab:sumo-resultados", "l l C C C C",
             ["Adversário", "Lado", "Vitórias", "Derrotas", "Empates", "Tempo médio até vencer (\\unit{\\second})"],
             linhas_sumo),
    "ctf": ("Resultados do rouba-bandeira em partidas de \\qty{5}{\\minute}, do ponto de vista da versão final. "
            "Valores somados nas partidas de cada condição.",
            "tab:ctf-resultados", "l l C C C C C",
            ["Adversário", "Lado", "Pontos pró", "Pontos contra", "Seguradas feitas", "Seguradas sofridas", "V / E / D"],
            linhas_ctf),
    "soccer": ("Resultados do futebol em partidas de \\qty{5}{\\minute}, do ponto de vista da versão final. "
               "Valores somados nas partidas de cada condição.",
               "tab:soccer-resultados", "l l C C C C",
               ["Adversário", "Lado", "Gols pró", "Gols contra", "Saldo", "V / E / D"],
               linhas_soccer),
}


def escrever(jogo, grupos, saida):
    legenda, rotulo, colunas, cabecalho, gerar = TABELAS[jogo]
    grupo = sorted(grupos.items(), key=lambda kv: (ORDEM.get(kv[0][0], 2), kv[0][0], kv[0][1]))
    contagem = ", ".join("%s, lado %d: %d" % (adv, lado, len(rs)) for (adv, lado), rs in grupo)
    texto = [
        "\\begin{table}[htbp]",
        "  \\centering",
        "  \\caption{%s}" % legenda,
        "  \\label{%s}" % rotulo,
        "  \\begin{tabelapsr}{@{\\hspace{6pt}}%s@{\\hspace{6pt}}}" % colunas,
        "    \\linhacab " + " & ".join("\\cab{%s}" % c for c in cabecalho) + " \\\\ \\hline",
    ]
    for linha in gerar(grupo):
        texto.append("    " + " & ".join(linha) + " \\\\ \\hline")
    texto += ["  \\end{tabelapsr}", "\\end{table}"]
    pasta = os.path.join(saida, "dados")
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, "tab_%s.tex" % jogo)
    with open(caminho, "w") as f:
        f.write("\n".join(texto) + "\n")
    print("tabela:", os.path.relpath(caminho, RAIZ), "(" + contagem + ")")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("arquivos", nargs="*")
    p.add_argument("--saida", default=os.path.join(RAIZ, "relatorio_final"))
    p.add_argument("--duracao", type=float, default=300.0)
    p.add_argument("--rodadas", type=int, default=20)
    args = p.parse_args()
    arquivos = args.arquivos or sorted(glob.glob(os.path.join(RAIZ, "exercicios/registro/logs/*.csv")))
    grupos = agrupar(arquivos, args.duracao, args.rodadas)
    for jogo in JOGOS:
        if jogo in grupos:
            escrever(jogo, grupos[jogo], args.saida)


if __name__ == "__main__":
    main()
