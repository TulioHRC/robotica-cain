# -*- coding: utf-8 -*-

# Macro Begin:

import os
import FreeCAD as App

DOC_NAME = "CaixaPlanetaria"
N_PLANETAS = 3            # deve ser igual ao valor de "n_planetas" na planilha

# ---------------------------------------------------------------------------
# Parâmetros de ENTRADA  (alias, valor, descrição)
# Valores idênticos ao modelo CaixaPlanetaria.FCStd de 05/09/2026.
# Números sem unidade: as expressões acrescentam "1 mm" / "1 deg".
# ---------------------------------------------------------------------------
PARAMS = [
    ("modulo",       1.5,  "módulo [mm]"),
    ("Zs",           12,   "dentes do sol"),
    ("Zp",           18,   "dentes de cada planeta"),
    ("n_planetas",   3,    "número de planetas (usado nas posições)"),
    ("alpha",        20,   "ângulo de pressão [graus]"),
    ("backlash",     0.3,  "folga de dente: arco no primitivo retirado de cada dente [mm]"),
    ("clearance",    0.25, "folga de fundo (x módulo)"),
    ("head_anel",   -0.4,  "alívio do adendo do anel (x módulo)"),
    ("espessura",    8.0,  "espessura (altura) das engrenagens [mm]"),
    ("furo_sol",     5.0,  "diâmetro do furo do sol [mm]"),
    ("furo_planeta", 4.3,  "diâmetro do furo dos planetas [mm]"),
    ("parede_anel",  4.0,  "parede do anel além do primitivo [mm]"),
    ("porta_d",      81.0, "diâmetro dos discos do porta-satélites [mm]"),
    ("porta_e",      4.0,  "espessura dos discos do porta-satélites [mm]"),
    ("porta_furo",   5.0,  "furo central do disco inferior [mm]"),
    ("porta_furo_sup", 6.5, "furo central do disco superior: passagem do eixo Ø6 da manivela [mm]"),
    ("pino_d",       4.0,  "diâmetro dos pinos dos planetas [mm]"),
    ("pino_h",       8.4,  "altura dos pinos acima do disco inferior [mm]"),
    ("folga_axial",  0.4,  "folga entre topo das engrenagens e disco superior [mm]"),
    # --- manivela (dimensões da manivela.stl original + correções)
    ("man_ajuste",   0.2,  "furo_sol - diâmetro da ponta: 0,2 = ajuste deslizante [mm]"),
    ("man_ponta_l",  6.2,  "comprimento da ponta que entra no sol [mm]"),
    ("man_eixo_d",   6.0,  "diâmetro do eixo acima da ponta [mm]"),
    ("man_eixo_l",   10.2, "comprimento do eixo, do ombro ao centro do braço [mm]"),
    ("man_braco",    50.0, "comprimento do braço, do eixo ao centro do punho [mm]"),
    ("man_braco_d",  6.0,  "diâmetro do braço [mm]"),
    ("man_punho_d",  8.0,  "diâmetro do punho [mm]"),
    ("man_punho_h",  22.0, "altura do punho acima do braço [mm]"),
    ("man_flat",     0.8,  "profundidade do chanfro em D na ponta e da nervura no sol (0 = redondo) [mm]"),
]

# ---------------------------------------------------------------------------
# Parâmetros DERIVADOS  (alias, fórmula da planilha, descrição)
# ---------------------------------------------------------------------------
DERIVADOS = [
    ("Zr",         "=Zs + 2 * Zp",                     "dentes do anel"),
    ("i_trans",    "=1 + Zr / Zs",                     "relação de transmissão (anel fixo)"),
    ("a_centros",  "=modulo * (Zs + Zp) / 2",               "distância entre centros sol-planeta [mm]"),
    ("d_s",        "=modulo * Zs",                          "diâmetro primitivo do sol [mm]"),
    ("d_p",        "=modulo * Zp",                          "diâmetro primitivo do planeta [mm]"),
    ("d_r",        "=modulo * Zr",                          "diâmetro primitivo do anel [mm]"),
    ("da_s",       "=modulo * (Zs + 2)",                    "diâmetro externo do sol [mm]"),
    ("da_p",       "=modulo * (Zp + 2)",                    "diâmetro externo do planeta [mm]"),
    ("da_r",       "=modulo * Zr - 2 * modulo * (1 + head_anel)", "diâmetro interno (adendo) do anel [mm]"),
    ("D_anel",     "=d_r + 2 * parede_anel",           "diâmetro externo do anel [mm]"),
    ("passo_ang",  "=360 / n_planetas",                         "espaçamento angular dos planetas [graus]"),
    ("check_mont", "=mod(Zs + Zr; n_planetas)",                 "condição de montagem: deve ser 0"),
    ("z_sup",      "=espessura + folga_axial",         "cota z do disco superior [mm]"),
    ("man_ponta_d", "=furo_sol - man_ajuste",          "diâmetro da ponta da manivela [mm]"),
    ("man_z_braco", "=man_ponta_l + man_eixo_l",       "cota do eixo do braço, medida da ponta [mm]"),
    ("man_z_montada", "=espessura - man_ponta_l",      "cota z da ponta com a manivela montada [mm]"),
    ("man_folga_tampa", "=espessura + man_eixo_l - man_braco_d / 2 - z_sup - porta_e",
                                                       "folga entre braço e disco superior (deve ser > 0) [mm]"),
    ("man_folga_disco", "=porta_furo_sup - man_eixo_d", "folga do eixo no disco superior (deve ser > 0) [mm]"),
]


# ===========================================================================
def _alias(sh, cell, alias):
    try:
        sh.setAlias(cell, alias)
    except Exception as e:
        raise RuntimeError("Alias inválido '%s' na célula %s: %s" % (alias, cell, e))


def criar_planilha(doc):
    sh = doc.addObject("Spreadsheet::Sheet", "Parametros")
    sh.set("A1", "Parâmetro"); sh.set("B1", "Valor"); sh.set("C1", "Descrição")
    row = 2
    for alias, val, desc in PARAMS:
        sh.set("A%d" % row, alias)
        sh.set("B%d" % row, str(val))
        _alias(sh, "B%d" % row, alias)
        sh.set("C%d" % row, desc)
        row += 1
    row += 1
    sh.set("A%d" % row, "— derivados —"); row += 1
    for alias, formula, desc in DERIVADOS:
        sh.set("A%d" % row, alias)
        sh.set("B%d" % row, formula)
        _alias(sh, "B%d" % row, alias)
        sh.set("C%d" % row, desc)
        row += 1
    try:
        sh.setColumnWidth("A", 110); sh.setColumnWidth("B", 90); sh.setColumnWidth("C", 380)
    except Exception:
        pass
    return sh


# ---------------------------------------------------------------- FCGear ---
def _fcgear():
    from freecad.gears.involutegear import InvoluteGear
    from freecad.gears.internalinvolutegear import InternalInvoluteGear
    try:
        from freecad.gears.basegear import ViewProviderGear
    except ImportError:
        ViewProviderGear = None
    return InvoluteGear, InternalInvoluteGear, ViewProviderGear


def nova_engrenagem(doc, nome, interna=False):
    InvoluteGear, InternalInvoluteGear, ViewProviderGear = _fcgear()
    obj = doc.addObject("Part::FeaturePython", nome)
    (InternalInvoluteGear if interna else InvoluteGear)(obj)
    if App.GuiUp and ViewProviderGear is not None:
        try:
            import freecad.gears as fg
            icon = os.path.join(os.path.dirname(fg.__file__), "icons",
                                "internalinvolutegear.svg" if interna else "involutegear.svg")
            ViewProviderGear(obj.ViewObject, icon)
        except Exception:
            try:
                ViewProviderGear(obj.ViewObject)
            except Exception:
                pass
    return obj


def vincular_engrenagem(g, alias_z, alias_furo=None):
    """Liga as propriedades do FCGear às células da planilha."""
    g.setExpression("module",         "Parametros.modulo * 1 mm")
    g.setExpression("num_teeth",      "Parametros.%s" % alias_z)
    g.setExpression("height",         "Parametros.espessura * 1 mm")
    g.setExpression("pressure_angle", "Parametros.alpha * 1 deg")
    g.setExpression("backlash",       "Parametros.backlash * 1 mm")
    g.setExpression("clearance",      "Parametros.clearance")
    if alias_furo:
        g.axle_hole = True
        g.setExpression("axle_holesize", "Parametros.%s * 1 mm" % alias_furo)


def pos_planeta(k):
    """Expressões (x, y) do k-ésimo planeta sobre a circunferência de raio a."""
    ang = "%d * Parametros.passo_ang * 1 deg" % k
    return ("Parametros.a_centros * 1 mm * cos(%s)" % ang,
            "Parametros.a_centros * 1 mm * sin(%s)" % ang)


# ------------------------------------------------------------- Part util ---
def cilindro(doc, nome, r_expr, h_expr, x=None, y=None, z=None):
    c = doc.addObject("Part::Cylinder", nome)
    c.setExpression("Radius", r_expr)
    c.setExpression("Height", h_expr)
    if x is not None: c.setExpression("Placement.Base.x", x)
    if y is not None: c.setExpression("Placement.Base.y", y)
    if z is not None: c.setExpression("Placement.Base.z", z)
    return c


def esconder(*objs):
    if not App.GuiUp:
        return
    for o in objs:
        try:
            o.ViewObject.Visibility = False
        except Exception:
            pass


def colorir(obj, rgb):
    if App.GuiUp:
        try:
            obj.ViewObject.ShapeColor = rgb
        except Exception:
            pass


# ------------------------------------------------------------ Manivela ----
def esfera(doc, nome, r_expr, x=None, z=None):
    e = doc.addObject("Part::Sphere", nome)
    e.setExpression("Radius", r_expr)
    if x is not None: e.setExpression("Placement.Base.x", x)
    if z is not None: e.setExpression("Placement.Base.z", z)
    return e


def manivela(doc, com_flat):
    """Manivela paramétrica em coordenadas locais (ponta em z = 0), montada
    pelo Placement do objeto final em z = espessura - man_ponta_l.
    Geometria igual à manivela.stl original: ponta cilíndrica que entra no
    sol, eixo vertical, esfera no cotovelo, braço horizontal, esfera na base
    do punho e punho vertical."""
    zb = "Parametros.man_z_braco * 1 mm"
    ponta = cilindro(doc, "MAN_ponta", "Parametros.man_ponta_d / 2 * 1 mm",
                     "Parametros.man_ponta_l * 1 mm", z="0 mm")
    eixo = cilindro(doc, "MAN_eixo", "Parametros.man_eixo_d / 2 * 1 mm",
                    "Parametros.man_eixo_l * 1 mm", z="Parametros.man_ponta_l * 1 mm")
    cotovelo = esfera(doc, "MAN_cotovelo", "Parametros.man_braco_d / 2 * 1 mm", z=zb)
    braco = cilindro(doc, "MAN_braco", "Parametros.man_braco_d / 2 * 1 mm",
                     "Parametros.man_braco * 1 mm", z=zb)
    pl = braco.Placement
    pl.Rotation = App.Rotation(App.Vector(0, 1, 0), 90)     # eixo do cilindro Z -> +X
    braco.Placement = pl
    base_punho = esfera(doc, "MAN_base_punho", "Parametros.man_punho_d / 2 * 1 mm",
                        x="Parametros.man_braco * 1 mm", z=zb)
    punho = cilindro(doc, "MAN_punho", "Parametros.man_punho_d / 2 * 1 mm",
                     "Parametros.man_punho_h * 1 mm",
                     x="Parametros.man_braco * 1 mm", z=zb)
    partes = [ponta, eixo, cotovelo, braco, base_punho, punho]

    if com_flat:
        fus = doc.addObject("Part::MultiFuse", "MAN_fusao")
        fus.Shapes = partes
        flat = doc.addObject("Part::Box", "MAN_flat")
        flat.setExpression("Length", "(Parametros.man_flat + 1) * 1 mm")
        flat.setExpression("Width",  "Parametros.man_ponta_d * 1 mm")
        flat.setExpression("Height", "(Parametros.man_ponta_l + 0.2) * 1 mm")
        flat.setExpression("Placement.Base.x", "(Parametros.man_ponta_d / 2 - Parametros.man_flat) * 1 mm")
        flat.setExpression("Placement.Base.y", "-Parametros.man_ponta_d / 2 * 1 mm")
        man = doc.addObject("Part::Cut", "Manivela")
        man.Base = fus
        man.Tool = flat
        partes += [fus, flat]
    else:
        man = doc.addObject("Part::MultiFuse", "Manivela")
        man.Shapes = partes
    man.setExpression("Placement.Base.z", "Parametros.man_z_montada * 1 mm")   # posição montada
    esconder(*partes)
    colorir(man, (0.30, 0.70, 0.40))
    return man


def sol_com_furo_D(doc, sol):
    """Se man_flat > 0, cria Sol_D = sol com o furo em D correspondente
    (uma nervura de profundidade man_flat dentro do furo redondo)."""
    nerv = doc.addObject("Part::Box", "SOL_nervura")
    nerv.setExpression("Length", "Parametros.man_flat * 1 mm")
    nerv.setExpression("Width",  "Parametros.furo_sol * 1 mm")
    nerv.setExpression("Height", "Parametros.espessura * 1 mm")
    nerv.setExpression("Placement.Base.x", "(Parametros.furo_sol / 2 - Parametros.man_flat) * 1 mm")
    nerv.setExpression("Placement.Base.y", "-Parametros.furo_sol / 2 * 1 mm")
    solD = doc.addObject("Part::MultiFuse", "Sol_D")
    solD.Shapes = [sol, nerv]
    esconder(nerv)
    colorir(solD, (0.95, 0.75, 0.20))
    return solD


# ===========================================================================
def construir():
    doc = App.newDocument(DOC_NAME)
    criar_planilha(doc)
    doc.recompute()

    # ---------------- Sol -------------------------------------------------
    sol = nova_engrenagem(doc, "Sol")
    vincular_engrenagem(sol, "Zs", "furo_sol")
    colorir(sol, (0.95, 0.75, 0.20))

    # ---------------- Anel (engrenagem interna) ---------------------------
    anel = nova_engrenagem(doc, "Anel", interna=True)
    vincular_engrenagem(anel, "Zr")
    anel.setExpression("thickness", "Parametros.parede_anel * 1 mm")
    anel.setExpression("head",      "Parametros.head_anel")
    # meio passo de rotação para colocar um dente do anel em fase com os planetas
    anel.setExpression("Placement.Rotation.Angle", "180 deg / Parametros.Zr")
    colorir(anel, (0.55, 0.60, 0.70))

    # ---------------- Planetas -------------------------------------------
    planetas = []
    for k in range(N_PLANETAS):
        p = nova_engrenagem(doc, "Planeta_%d" % (k + 1))
        vincular_engrenagem(p, "Zp", "furo_planeta")
        x, y = pos_planeta(k)
        p.setExpression("Placement.Base.x", x)
        p.setExpression("Placement.Base.y", y)
        # meio passo (180°/Zp): o vão do planeta fica de frente para o dente do sol
        p.setExpression("Placement.Rotation.Angle", "180 deg / Parametros.Zp")
        colorir(p, (0.30, 0.65, 0.90))
        planetas.append(p)

    # ---------------- Porta-satélites inferior (disco + pinos - furo) -----
    disco_inf = cilindro(doc, "PS_inf_disco",
                         "Parametros.porta_d / 2 * 1 mm", "Parametros.porta_e * 1 mm",
                         z="-Parametros.porta_e * 1 mm")
    pinos = []
    for k in range(N_PLANETAS):
        x, y = pos_planeta(k)
        pinos.append(cilindro(doc, "PS_inf_pino_%d" % (k + 1),
                              "Parametros.pino_d / 2 * 1 mm", "Parametros.pino_h * 1 mm",
                              x=x, y=y, z="0 mm"))
    furo_inf = cilindro(doc, "PS_inf_furo",
                        "Parametros.porta_furo / 2 * 1 mm", "(Parametros.porta_e + 2) * 1 mm",
                        z="-(Parametros.porta_e + 1) * 1 mm")
    fus_inf = doc.addObject("Part::MultiFuse", "PS_inf_fusao")
    fus_inf.Shapes = [disco_inf] + pinos
    inferior = doc.addObject("Part::Cut", "PortaSatelites_Inferior")
    inferior.Base = fus_inf
    inferior.Tool = furo_inf
    esconder(disco_inf, furo_inf, fus_inf, *pinos)
    colorir(inferior, (0.85, 0.35, 0.30))

    # ---------------- Porta-satélites superior (disco - furos) ------------
    disco_sup = cilindro(doc, "PS_sup_disco",
                         "Parametros.porta_d / 2 * 1 mm", "Parametros.porta_e * 1 mm",
                         z="Parametros.z_sup * 1 mm")
    furos_sup = [cilindro(doc, "PS_sup_furo_central",
                          "Parametros.porta_furo_sup / 2 * 1 mm", "(Parametros.porta_e + 2) * 1 mm",
                          z="(Parametros.z_sup - 1) * 1 mm")]
    for k in range(N_PLANETAS):
        x, y = pos_planeta(k)
        furos_sup.append(cilindro(doc, "PS_sup_furo_%d" % (k + 1),
                                  "Parametros.furo_planeta / 2 * 1 mm",
                                  "(Parametros.porta_e + 2) * 1 mm",
                                  x=x, y=y, z="(Parametros.z_sup - 1) * 1 mm"))
    fus_furos = doc.addObject("Part::MultiFuse", "PS_sup_furos")
    fus_furos.Shapes = furos_sup
    superior = doc.addObject("Part::Cut", "PortaSatelites_Superior")
    superior.Base = disco_sup
    superior.Tool = fus_furos
    esconder(disco_sup, fus_furos, *furos_sup)
    colorir(superior, (0.85, 0.35, 0.30))
    if App.GuiUp:
        try:
            superior.ViewObject.Transparency = 60
        except Exception:
            pass

    doc.recompute()

    # ---------------- Manivela ------------------------------------------
    man_flat = dict((k, v) for k, v, _ in PARAMS)["man_flat"] > 0
    manivela(doc, com_flat=man_flat)
    if man_flat:
        sol_com_furo_D(doc, sol)      # exporte Sol_D (furo em D) em vez de Sol
        esconder(sol)
    doc.recompute()

    # ---------------- Relatório no console -------------------------------
    sh = doc.getObject("Parametros")
    def g(a):
        try:
            return sh.get(a)
        except Exception:
            return "?"
    App.Console.PrintMessage(
        "\n=== CaixaPlanetaria gerada ===\n"
        "  Zs=%s  Zp=%s  Zr=%s  n=%s  ->  i = %s\n"
        "  a = %s mm   d_s=%s  d_p=%s  d_r=%s mm\n"
        "  da_s=%s  da_p=%s  da_r=%s  D_anel=%s mm\n"
        "  (Zs+Zr) mod n = %s  (0 = montável com espaçamento uniforme)\n"
        "  Manivela: ponta Ø%s em furo Ø%s | folga eixo/disco sup. %s mm | folga braço/tampa %s mm\n"
        % (g("Zs"), g("Zp"), g("Zr"), g("n_planetas"), g("i_trans"), g("a_centros"), g("d_s"), g("d_p"),
           g("d_r"), g("da_s"), g("da_p"), g("da_r"), g("D_anel"), g("check_mont"),
           g("man_ponta_d"), g("furo_sol"), g("man_folga_disco"), g("man_folga_tampa")))
    try:
        if float(g("check_mont")) != 0:
            App.Console.PrintWarning("ATENÇÃO: (Zs+Zr) não é divisível por n.\n")
        if float(g("man_folga_disco")) <= 0:
            App.Console.PrintWarning("ATENÇÃO: eixo da manivela não passa pelo disco superior (porta_furo_sup).\n")
        if float(g("man_folga_tampa")) <= 0:
            App.Console.PrintWarning("ATENÇÃO: braço da manivela colide com o disco superior (man_eixo_l).\n")
    except Exception:
        pass

    if App.GuiUp:
        import FreeCADGui as Gui
        Gui.SendMsgToActiveView("ViewFit")
        try:
            Gui.activeDocument().activeView().viewIsometric()
        except Exception:
            pass
    return doc


def _main():
    import traceback
    try:
        construir()
    except Exception:
        tb = traceback.format_exc()
        App.Console.PrintError(tb + "\n")
        if App.GuiUp:
            try:
                from PySide import QtWidgets
                QtWidgets.QMessageBox.critical(None, "CaixaPlanetaria.FCMacro",
                    "A macro falhou. Copie a mensagem abaixo:\n\n" + tb)
            except Exception:
                pass
        raise


_main()
