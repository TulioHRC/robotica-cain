import ast
import glob
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MENSAGENS = {"geometry_msgs", "nav_msgs", "sensor_msgs", "std_msgs"}
PERMITIDOS = {"numpy", "rospy"} | MENSAGENS
PARAMETROS = {"sumo": ["~robot", "~opponent"], "ctf": ["~robot", "~team", "~role", "~opponents"],
              "soccer": ["~team"]}


def stdlib():
    if hasattr(sys, "stdlib_module_names"):
        return set(sys.stdlib_module_names)
    return {"math", "random", "time", "json", "collections", "itertools", "functools", "os", "sys",
            "csv", "enum", "dataclasses", "typing", "copy", "heapq", "bisect", "statistics", "operator"}


def arquivos_da_equipe():
    nomes = set()
    for caminho in glob.glob(os.path.join(RAIZ, "exercicios", "**", "*.py"), recursive=True):
        nomes.add(os.path.splitext(os.path.basename(caminho))[0])
    return nomes


def literais(arvore):
    return {n.value for n in ast.walk(arvore) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def topico(no):
    if isinstance(no, ast.Constant) and isinstance(no.value, str):
        return no.value
    if isinstance(no, ast.BinOp) and isinstance(no.left, ast.Constant):
        return str(no.left.value)
    if isinstance(no, ast.JoinedStr):
        return "".join(v.value for v in no.values if isinstance(v, ast.Constant))
    if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute) and isinstance(no.func.value, ast.Constant):
        return str(no.func.value.value)
    return "?"


def verificar(jogo):
    caminho = os.path.join(RAIZ, "exercicios", jogo, jogo + ".py")
    if not os.path.exists(caminho):
        return [("arquivo existe", False, os.path.relpath(caminho, RAIZ))]
    with open(caminho) as f:
        arvore = ast.parse(f.read())
    padrao = stdlib()
    equipe = arquivos_da_equipe() - padrao - PERMITIDOS
    proibidos = []
    da_equipe = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes = [a.name for a in no.names]
        elif isinstance(no, ast.ImportFrom):
            if no.level:
                proibidos.append("." * no.level + (no.module or ""))
                continue
            if no.module == "psr_hero" and all(a.name == "utils" for a in no.names):
                continue
            nomes = [no.module]
        else:
            continue
        for nome in nomes:
            raiz = nome.split(".")[0]
            if nome == "psr_hero.utils" or raiz in padrao or raiz in PERMITIDOS:
                continue
            if raiz in equipe:
                da_equipe.append(nome)
            else:
                proibidos.append(nome)
    publicadores = []
    teclado = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call):
            f = no.func
            nome = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            if nome == "Publisher" and no.args:
                publicadores.append(topico(no.args[0]))
            if nome in ("input", "raw_input") or (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Attribute)
                                                  and f.value.attr == "stdin"):
                teclado.append(nome)
    fora = [t for t in publicadores if "cmd_vel" not in t]
    textos = literais(arvore)
    faltando = [p for p in PARAMETROS[jogo] if p not in textos]
    return [
        ("arquivo existe", True, os.path.relpath(caminho, RAIZ)),
        ("só imports permitidos", not proibidos, ", ".join(proibidos)),
        ("não depende de arquivos da equipe", not da_equipe, ", ".join(da_equipe)),
        ("publica só em cmd_vel", bool(publicadores) and not fora, ", ".join(publicadores) or "nenhum publicador"),
        ("sem leitura do teclado", not teclado, ", ".join(teclado)),
        ("lê os parâmetros de lado", not faltando, ", ".join(faltando)),
    ]


def main():
    jogos = sys.argv[1:] or ["sumo", "ctf", "soccer"]
    tudo_ok = True
    for jogo in jogos:
        print("==", jogo)
        for regra, ok, detalhe in verificar(jogo):
            tudo_ok = tudo_ok and ok
            print("  [%s] %s%s" % ("ok" if ok else "FALHA", regra, ("  (" + detalhe + ")") if detalhe and not ok else ""))
    print("todas as regras atendidas" if tudo_ok else "há regras não atendidas")
    sys.exit(0 if tudo_ok else 1)


if __name__ == "__main__":
    main()
