#!/usr/bin/env python3
"""Capture the flag (rouba-bandeira). One file drives every robot of your team.

The arena is 1.6 x 1.6 m, split at x = 0. Blue (base on the left, x = -0.62 m) has
hero_0 and hero_1; red (base on the right, x = +0.62 m) has hero_2 and hero_3.
(With two robots: hero_0 is blue and hero_1 is red.) In a team of two, one robot
is the attacker and the other the defender (parameter ~role).

Rules
  * Touch the enemy flag (< 0.07 m) and you carry it. It follows you.
  * Carry it into your base circle (radius 0.14 m around your flag) to score a point.
  * Inside YOUR half, touching an opponent (< 0.10 m) HOLDS it still for 4 s. If it was
    carrying your flag, the flag returns to your base. A held robot cannot hold others,
    and after the release it is immune for 1.5 s.
  * In the opponents' half you are the one who can be held.
  * 90 s without a point is a draw and everyone goes back to the start.

Estratégia (versão final)
-------------------------
Todo o cálculo é feito no "referencial do time": o time vermelho gira o mundo de 180°
(x -> -x, y -> -y, yaw -> yaw + pi), então a nossa base fica sempre em (-0.62, 0) e a
nossa metade é sempre x < 0. Uma rotação não troca o sentido de giro, então o comando
(v, w) calculado vale direto no mundo. Assim o mesmo código serve para azul e vermelho.

Atacante (máquina de estados, prioridade de cima para baixo):
  VOLTAR       carregando a bandeira: vai para a base, desviando dos adversários.
  IMUNE        acabou de ser solto (1.5 s de imunidade): se dá para tocar a bandeira
               nesse tempo, vai direto; senão foge para a nossa metade (RECUAR).
  CACAR        um adversário está na nossa metade, a menos de HUNT_R: na nossa metade
               quem segura somos nós, então vale encostar nele.
  RECUAR       um adversário chegou a menos de RETREAT_IN na metade dele: volta para a
               nossa metade (desviando) até ele ficar a mais de RETREAT_OUT.
  ESPREITAR    o defensor inimigo está acampado na bandeira: espera na linha do meio,
               do lado oposto ao dele, por ESPREITAR_T s (isca: se ele cruzar, é segurado).
  ATACAR       vai para a bandeira inimiga desviando. Contra um guarda acampado que não
               sai, depois de ATAQUE_T s tenta sem desvio (TUDO_OU_NADA) e o ciclo recomeça.
Defensor (prioridade de cima para baixo):
  RESGATAR     a nossa bandeira saiu da base: persegue o portador (com antecipação)
               enquanto ele estiver na nossa metade.
  INTERCEPTAR  há um adversário na nossa metade: persegue o mais próximo da bandeira.
  MARCAR       há um adversário segurado na nossa metade: fica colado nele (MARK_D) para
               segurar de novo no instante em que a imunidade acabar. Sem a bandeira, fica
               entre ele e a nossa bandeira (bloqueio de corpo durante a imunidade). Com a
               bandeira (o juiz deixa um robô segurado pegá-la de novo a < 7 cm), fica no
               caminho de fuga dele. Empurrar aqui é intencional: sem checagem de encalhe.
  GUARDAR      fica no segmento entre a bandeira e o adversário mais próximo dela, a
               GUARD_R da bandeira, sem cruzar a linha do meio.
Os dois: um robô segurado (campo "held" de /game/state) não manda comando, e um robô
que tenta andar e não sai do lugar por 1.5 s dá ré girando (desencalhar).

Tempo: o simulador pode rodar mais devagar que o relógio (~0.4x sem placa de vídeo) e
as regras contam tempo de jogo. clock() soma os passos do round_time de /game/state e
mede a razão jogo/parede; todos os temporizadores e velocidades usam esse relógio.

Desvio (steer): testa N_DIR direções; para cada uma prevê a nossa posição a V_MAX em
0.3, 0.6 e 1.0 s e a folga até cada adversário na metade dele (um adversário ativo é
tratado como perseguidor que também se aproxima). Escolhe a direção com a maior
pontuação: avanço para a meta - penalidade por folga pequena - giro necessário - parede.

Controlador (ir até um ponto, uniciclo, pode andar de ré):
  e = erro de orientação para o alvo (usando a traseira se |e| > 90°, com histerese)
  w = K_W * e                (saturado em W_MAX)
  v = min(K_V * d, V_MAX) * cos(e)   (zero se cos(e) < 0)

Run:  ./run.sh run ctf      (see README.md in this folder)
"""
import json
import math
import re

import rospy
from geometry_msgs.msg import PointStamped, Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Bool, String

from psr_hero.utils import V_MAX, W_MAX, clamp, pose_from_odom, wrap_angle

BASE_X = 0.62  # m, blue at -BASE_X, red at +BASE_X
BASE_RADIUS = 0.14  # m

# ---- arena e regras (referencial do time: nossa base em x < 0) ----
HOME = (-BASE_X, 0.0)
ARENA = 0.80          # meia largura da arena (m)
WALL_MARGIN = 0.08    # alvos ficam pelo menos a esta distância das paredes
TAG_DIST = 0.10       # distância de captura (m)
MID_SAFE = 0.04       # o defensor e o caçador não passam de x = -MID_SAFE
ENEMY_HALF = -0.05    # adversário com x > ENEMY_HALF pode nos segurar

# ---- controlador ----
K_V = 1.5             # 1/s: v = K_V * distância
K_W = 3.5             # 1/s: w = K_W * erro de orientação
REV_HYST = 0.35       # rad: histerese para trocar entre frente e ré
STOP_DIST = 0.015     # m: chegou ao alvo

# ---- desvio (escolha de direção por amostragem) ----
N_DIR = 24            # direções testadas
TAUS = (0.3, 0.6, 1.0)  # s: horizontes de previsão
SENSE_R = 0.45        # m: só considera adversários a menos disso
C_SAFE = 0.25         # m: folga desejada
PURSUIT = 0.8         # fração de V_MAX que um adversário ativo anda na nossa direção
ACTIVE_T = 2.0        # s: adversário que se moveu há menos disso é "ativo"
W_GOAL = 1.0
W_SAFE = 3.0
W_TAG = 10.0
W_TURN = 0.3
W_WALL = 2.0
LOOKAHEAD = 0.20      # m: distância do ponto intermediário

# ---- atacante ----
HUNT_R = 0.25         # m: caça adversário na nossa metade até esta distância
GUARD_CAMP_R = 0.18   # m: adversário a menos disso da bandeira = guarda acampado
LURK_X = -0.10        # m: ponto de espera na linha do meio
LURK_Y = 0.45
ESPREITAR_T = 5.0     # s esperando a isca
ATAQUE_T = 6.0        # s tentando com desvio
TUDO_T = 4.0          # s tentando sem desvio
IMMUNE_T = 1.5        # s de imunidade depois de ser solto (regra)
RETREAT_IN = 0.17     # m: adversário mais perto que isso na metade dele -> recuar
RETREAT_OUT = 0.30    # m: volta a atacar quando ele estiver mais longe que isso

# ---- defensor ----
GUARD_R = 0.22        # m: distância da guarda até a bandeira
INTERCEPT_LEAD = 0.6  # fração do tempo de chegada usada para antecipar o alvo
INTERCEPT_MAX = 0.8   # s: antecipação máxima
INTRUDER_X = -0.02    # adversário com x < INTRUDER_X está na nossa metade
MARK_D = 0.085        # m: marcação colada no adversário segurado (contato ~0.07 m)

# ---- desencalhar ----
STUCK_V = 0.06        # m/s: comando mínimo para checar se travou
STUCK_T = 1.5         # s parado tentando andar
STUCK_MOVE = 0.02     # m
RECOVER_T = 0.7       # s de manobra
CONTACT_MODES = ("interceptar", "resgatar", "marcar", "cacar", "imune", "tudo_ou_nada")
PAUSE_T = 3.0         # s ignorando encalhe depois de um ponto/empate (o juiz pausa 2 s)
RT_FROZEN_T = 0.5     # s sem o round_time mudar = jogo pausado


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def clamp_arena(p, margin=WALL_MARGIN):
    lim = ARENA - margin
    return (clamp(p[0], -lim, lim), clamp(p[1], -lim, lim))


def parse_ids(obj):
    """Ids de robôs em um campo do /game/state (lista de ids ou nomes, lista de bool, dict)."""
    ids = set()
    if isinstance(obj, dict):
        items = [k for k, v in obj.items() if v not in (False, 0, None, "", [])]
    elif isinstance(obj, (list, tuple)):
        if obj and all(isinstance(v, bool) for v in obj):
            return {i for i, v in enumerate(obj) if v}
        items = list(obj)
    elif isinstance(obj, (int, str)) and not isinstance(obj, bool):
        items = [obj]
    else:
        return ids
    for it in items:
        if isinstance(it, bool):
            continue
        if isinstance(it, (int, float)):
            ids.add(int(it))
        elif isinstance(it, str):
            digits = re.findall(r"\d+", it)
            if digits:
                ids.add(int(digits[-1]))
        elif isinstance(it, dict):
            for key in ("id", "robot", "name"):
                if key in it:
                    ids |= parse_ids([it[key]])
                    break
    return ids


class Opp(object):
    __slots__ = ("id", "x", "y", "vx", "vy", "held")

    def __init__(self, k, x, y, vx, vy, held):
        self.id, self.x, self.y, self.vx, self.vy, self.held = k, x, y, vx, vy, held

    @property
    def p(self):
        return (self.x, self.y)


class CaptureTheFlag:
    def __init__(self):
        rospy.init_node("ctf")
        self.robot = rospy.get_param("~robot", 0)
        self.team = rospy.get_param("~team", "blue" if self.robot == 0 else "red")
        self.role = rospy.get_param("~role", "attacker")
        self.opponents = list(rospy.get_param("~opponents", [1 if self.robot == 0 else 0]))
        self.blue = self.team == "blue"
        self.home = (-BASE_X if self.blue else BASE_X, 0.0)  # your base and your flag
        self.sgn = 1.0 if self.blue else -1.0  # mundo -> referencial do time
        self.me = None  # (x, y, yaw)
        self.opp = {}  # opponent id -> (x, y, yaw)
        self.opp_vel = {}  # opponent id -> (vx, vy), estimada por diferenças finitas
        self.opp_last = {}  # opponent id -> (x, y, t)
        self.enemy_flag = None  # (x, y)
        self.own_flag = None  # (x, y): away from self.home means an opponent has it
        self.carrying = False  # True while you hold the enemy flag
        self.held = set()  # ids dos robôs segurados (/game/state)
        self.released = {}  # id -> instante em que foi solto (imune por IMMUNE_T)
        self.last_rt = None  # round_time anterior (/game/state)
        self.rt_change_wall = None  # relógio de parede quando o round_time mudou
        self.game_t = 0.0  # tempo de jogo acumulado (s)
        self.game_wall = None  # relógio de parede da última atualização de game_t
        self.rtf = 1.0  # razão tempo de jogo / tempo de parede
        self.rtf_mark = None
        self.last_score = None
        self.pause_until = 0.0  # pausa do juiz depois de ponto/empate

        # estado interno da máquina de estados e do controlador
        self.mode = "inicio"
        self.reverse = False
        self.cycle_t0 = None  # início do ciclo espreitar/atacar/tudo-ou-nada
        self.stuck_ref = None  # (x, y, t)
        self.recover_until = 0.0
        self.recover_dir = 1.0
        self.was_held = False
        self.retreating = False
        self.opp_active = {}  # id -> último instante em que o adversário se moveu

        self.pub = rospy.Publisher("/hero_%d/cmd_vel" % self.robot, Twist, queue_size=1)

        # TODO 1 (ROS): assinaturas
        rospy.Subscriber("/hero_%d/odom" % self.robot, Odometry, self.on_me, queue_size=1)
        for k in self.opponents:
            rospy.Subscriber("/hero_%d/odom" % k, Odometry, self.on_opp, callback_args=k, queue_size=1)
        enemy, own = ("red", "blue") if self.blue else ("blue", "red")
        rospy.Subscriber("/flag/%s" % enemy, PointStamped, self.on_enemy_flag, queue_size=1)
        rospy.Subscriber("/flag/%s" % own, PointStamped, self.on_own_flag, queue_size=1)
        rospy.Subscriber("/hero_%d/has_flag" % self.robot, Bool, self.on_has_flag, queue_size=1)
        rospy.Subscriber("/game/state", String, self.on_state, queue_size=1)
        rospy.loginfo("ctf: hero_%d time %s papel %s adversarios %s",
                      self.robot, self.team, self.role, self.opponents)

    # ------------------------------------------------------------------ callbacks
    def on_me(self, msg):
        self.me = pose_from_odom(msg)

    def on_opp(self, msg, k):
        pose = pose_from_odom(msg)
        wall = rospy.get_time()
        now = self.clock()
        last = self.opp_last.get(k)
        if last is not None:
            dt = (wall - last[2]) * self.rtf  # em segundos de jogo
            if dt > 1e-3:
                vx, vy = (pose[0] - last[0]) / dt, (pose[1] - last[1]) / dt
                if math.hypot(vx, vy) > 0.5:  # salto (robô recolocado): zera
                    vx, vy = 0.0, 0.0
                ovx, ovy = self.opp_vel.get(k, (0.0, 0.0))
                a = 0.3  # filtro passa-baixa
                self.opp_vel[k] = (ovx + a * (vx - ovx), ovy + a * (vy - ovy))
                if math.hypot(*self.opp_vel[k]) > 0.03:
                    self.opp_active[k] = now
        self.opp_last[k] = (pose[0], pose[1], wall)
        self.opp[k] = pose

    def on_enemy_flag(self, msg):
        self.enemy_flag = (msg.point.x, msg.point.y)

    def on_own_flag(self, msg):
        self.own_flag = (msg.point.x, msg.point.y)

    def on_has_flag(self, msg):
        self.carrying = msg.data

    def on_state(self, msg):
        try:
            data = json.loads(msg.data)
            held = parse_ids(data.get("held")) if isinstance(data, dict) else set()
        except Exception:  # formato inesperado: segue sem a informação
            held = set()
        wall = rospy.get_time()
        try:
            rt, score = data.get("round_time"), data.get("score")
        except Exception:
            rt, score = None, None
        # Relógio do jogo. O simulador pode rodar mais devagar que o relógio de parede
        # (sem placa de vídeo, ~0.4x), e as regras (imunidade de 1.5 s, segurar por 4 s)
        # contam tempo de jogo. O round_time de /game/state anda em passos de 0.1 s de
        # jogo: somamos esses passos e medimos a razão jogo/parede (self.rtf).
        if isinstance(rt, (int, float)):
            if self.last_rt is not None:
                d = rt - self.last_rt
                if 0.0 < d < 1.0:
                    self.game_t += d
                    self.game_wall = wall
                    if self.rtf_mark is None:
                        self.rtf_mark = (wall, self.game_t)
                    elif wall - self.rtf_mark[0] >= 1.0:
                        sample = (self.game_t - self.rtf_mark[1]) / (wall - self.rtf_mark[0])
                        self.rtf = clamp(0.6 * self.rtf + 0.4 * sample, 0.05, 2.0)
                        self.rtf_mark = (wall, self.game_t)
                elif d != 0.0:  # nova rodada: o round_time voltou a zero
                    self.rtf_mark = None
                    self.pause_until = self.game_t + PAUSE_T
                else:  # parado (pausa do juiz): não mede a razão neste trecho
                    self.rtf_mark = None
            if rt != self.last_rt:
                self.rt_change_wall = wall
            self.last_rt = rt
        now = self.clock()
        for k in self.held - held:  # acabou de ser solto: imune por IMMUNE_T
            self.released[k] = now
        self.held = held
        # pausa do juiz (2 s depois de um ponto ou empate, com os robôs congelados): o
        # round_time para ou volta a zero e o placar muda. Nesse tempo não checamos encalhe.
        if score is not None and score != self.last_score:
            if self.last_score is not None:
                self.pause_until = now + PAUSE_T
            self.last_score = score

    def clock(self):
        """Tempo de jogo (s). Sem /game/state, usa o relógio de parede."""
        wall = rospy.get_time()
        if self.game_wall is None:
            return wall
        return self.game_t + min((wall - self.game_wall) * self.rtf, 0.1)

    def game_paused(self, now):
        if now < self.pause_until:
            return True
        if self.rt_change_wall is None:
            return False
        frozen = max(RT_FROZEN_T, 3 * 0.1 / self.rtf)  # 3 passos do round_time sem mudar
        return rospy.get_time() - self.rt_change_wall > frozen

    def immune(self, k, now):
        return now - self.released.get(k, -1e9) < IMMUNE_T

    # ------------------------------------------------------------------ referencial do time
    def to_team(self, x, y, yaw=0.0):
        if self.blue:
            return (x, y, yaw)
        return (-x, -y, wrap_angle(yaw + math.pi))

    # ------------------------------------------------------------------ decisão
    def compute_command(self, me, opponents, enemy_flag, own_flag, carrying):
        """Devolve (linear_x, angular_z). `opponents` vem do modelo; usamos self.opp (com ids)."""
        now = self.clock()
        me_t = self.to_team(*me)
        ef = self.to_team(*enemy_flag)[:2]
        of = self.to_team(*own_flag)[:2]
        opps = []
        for k, pose in list(self.opp.items()):
            x, y, _ = self.to_team(*pose)
            vx, vy = self.opp_vel.get(k, (0.0, 0.0))
            opps.append(Opp(k, x, y, self.sgn * vx, self.sgn * vy, k in self.held))

        if self.robot in self.held:  # segurado: os comandos são ignorados
            self.mode = "segurado"
            self.was_held = True
            self.stuck_ref = None
            self.recover_until = 0.0
            return 0.0, 0.0
        if self.was_held:  # acabou de ser solto: recomeça o ciclo de ataque
            self.was_held = False
            self.cycle_t0 = None

        if self.role == "defender":
            target, threats, mode = self.defend(me_t, opps, of)
        else:
            target, threats, mode = self.attack(me_t, opps, ef, carrying, now)
        if mode != self.mode:
            rospy.loginfo("hero_%d: %s -> %s", self.robot, self.mode, mode)
            self.mode = mode

        if threats:
            target = self.steer(me_t, target, threats, now)
        v, w = self.drive(me_t, target)
        if mode in CONTACT_MODES:  # empurrar o adversário é intencional, não é encalhe
            self.stuck_ref = None
            self.recover_until = 0.0
            return v, w
        return self.unstick(me_t, v, w, now)

    def attack(self, me, opps, ef, carrying, now):
        threats = [o for o in opps if not o.held and o.x > ENEMY_HALF]
        in_enemy_half = me[0] > ENEMY_HALF - 0.05

        if carrying:
            self.cycle_t0 = None
            self.retreating = False
            return HOME, threats, "voltar"

        # recém-solto e imune: se dá para chegar à bandeira dentro da imunidade, vai direto;
        # senão aproveita a imunidade para sair da metade inimiga
        left = IMMUNE_T - (now - self.released.get(self.robot, -1e9))
        if left > 0 and in_enemy_half:
            if dist(me, ef) < V_MAX * left + 0.05:
                return ef, [], "imune"
            self.retreating = True

        # na nossa metade nós é que seguramos: caça quem estiver perto
        if me[0] < -MID_SAFE:
            prey = [o for o in opps if not o.held and o.x < INTRUDER_X and dist(me, o.p) < HUNT_R
                    and not self.immune(o.id, now)]
            if prey:
                o = min(prey, key=lambda q: dist(me, q.p))
                return self.intercept(me, o), [], "cacar"

        # perseguido de perto na metade inimiga (e longe da bandeira): foge para a nossa metade
        near = min([dist(me, o.p) for o in threats] or [1.0])
        if in_enemy_half and near < RETREAT_IN and dist(me, ef) > 0.12:
            self.retreating = True
        if self.retreating and (near > RETREAT_OUT or me[0] < ENEMY_HALF - 0.10):
            self.retreating = False
        if self.retreating:
            return (-0.30, me[1]), threats, "recuar"

        guards = [o for o in threats if dist(o.p, ef) < GUARD_CAMP_R]
        if not guards:
            self.cycle_t0 = None
            return ef, threats, "atacar"

        # guarda acampado na bandeira: espera (isca), tenta com desvio, tenta sem desvio
        if self.cycle_t0 is None:
            self.cycle_t0 = now
        t = (now - self.cycle_t0) % (ESPREITAR_T + ATAQUE_T + TUDO_T)
        if t < ESPREITAR_T and dist(me, ef) > 0.35:
            g = min(guards, key=lambda q: dist(q.p, ef))
            side = -1.0 if g.y > 0.02 else 1.0
            return (LURK_X, side * LURK_Y), [], "espreitar"
        if t < ESPREITAR_T + ATAQUE_T:
            return ef, threats, "atacar"
        return ef, [], "tudo_ou_nada"

    def defend(self, me, opps, of):
        active = [o for o in opps if not o.held]
        if dist(of, HOME) > 0.04 and opps:  # nossa bandeira saiu da base
            carrier = min(opps, key=lambda q: dist(q.p, of))
            if carrier.x < INTRUDER_X and not carrier.held:
                return self.intercept(me, carrier), [], "resgatar"

        intruders = [o for o in active if o.x < INTRUDER_X]
        if intruders:
            o = min(intruders, key=lambda q: dist(q.p, HOME))
            return self.intercept(me, o), [], "interceptar"

        # adversário segurado na nossa metade: fica colado nele (MARK_D), para segurar de
        # novo no instante em que a imunidade acabar. Sem a bandeira, ficamos entre ele e a
        # nossa bandeira (bloqueio de corpo durante os 1.5 s em que ele é imune). Com a
        # bandeira (o juiz deixa um robô segurado pegá-la de novo se estiver a < 7 cm),
        # ficamos no caminho de fuga dele, entre ele e a base adversária.
        held_in = [o for o in opps if o.held and o.x < INTRUDER_X]
        if held_in:
            o = min(held_in, key=lambda q: dist(q.p, HOME))
            ref = (BASE_X, 0.0) if dist(of, o.p) < 0.06 else HOME
            dx, dy = ref[0] - o.x, ref[1] - o.y
            n = math.hypot(dx, dy) or 1.0
            p = (o.x + MARK_D * dx / n, o.y + MARK_D * dy / n)
            return clamp_arena((min(p[0], -MID_SAFE), p[1])), [], "marcar"

        if active:
            ref = min(active, key=lambda q: dist(q.p, HOME)).p
        else:
            ref = (0.0, 0.0)
        dx, dy = ref[0] - HOME[0], ref[1] - HOME[1]
        n = math.hypot(dx, dy) or 1.0
        p = (HOME[0] + GUARD_R * dx / n, HOME[1] + GUARD_R * dy / n)
        p = (min(p[0], -MID_SAFE - 0.05), p[1])
        return clamp_arena(p), [], "guardar"

    def intercept(self, me, o):
        """Ponto de interceptação: posição prevista do adversário, sem sair da nossa metade."""
        d = dist(me, o.p)
        lead = clamp(INTERCEPT_LEAD * d / V_MAX, 0.0, INTERCEPT_MAX)
        p = (o.x + lead * o.vx, o.y + lead * o.vy)
        p = (min(p[0], -MID_SAFE), p[1])
        return clamp_arena(p, 0.04)

    # ------------------------------------------------------------------ desvio
    def steer(self, me, goal, threats, now):
        """Escolhe a direção de movimento por amostragem (parecido com uma janela dinâmica).

        Para cada uma de N_DIR direções, simula o robô andando a V_MAX por TAUS segundos e
        mede a folga até cada adversário. Um adversário ativo é tratado como perseguidor:
        ele também anda V_MAX * tau na nossa direção, então a folga é |p_eu - p_adv| - V_MAX*tau.
        Pontuação = W_GOAL*cos(ângulo até a meta) - W_SAFE*penalidade(folga)
                    - W_TURN*giro necessário (frente ou ré) - penalidade de parede.
        Posições previstas na nossa metade não são penalizadas (lá ninguém nos segura).
        """
        gx, gy = goal[0] - me[0], goal[1] - me[1]
        dg = math.hypot(gx, gy)
        if dg < 1e-6:
            return goal
        close = [o for o in threats if dist(me, o.p) < SENSE_R]
        if not close:
            return goal
        th_goal = math.atan2(gy, gx)
        best, best_th = -1e9, th_goal
        for i in range(N_DIR):
            th = th_goal + 2.0 * math.pi * i / N_DIR
            c, s_ = math.cos(th), math.sin(th)
            score = W_GOAL * math.cos(th - th_goal)
            ang = abs(wrap_angle(th - me[2]))
            score -= W_TURN * min(ang, math.pi - ang) / (math.pi / 2)
            for tau in TAUS:
                step = min(V_MAX * tau, dg + 0.05)
                px, py = me[0] + step * c, me[1] + step * s_
                lim = ARENA - 0.06
                out = max(abs(px) - lim, abs(py) - lim, 0.0)
                score -= W_WALL * out / 0.05
                if px < ENEMY_HALF - 0.03:  # nossa metade: seguro
                    continue
                for o in close:
                    gap = math.hypot(px - o.x, py - o.y)
                    if now - self.opp_active.get(o.id, -1e9) < ACTIVE_T:
                        gap -= V_MAX * tau * PURSUIT
                    if gap < C_SAFE:
                        score -= W_SAFE * ((C_SAFE - gap) / C_SAFE) ** 2
                    if gap < TAG_DIST:
                        score -= W_TAG
            if score > best:
                best, best_th = score, th
        L = min(LOOKAHEAD, max(dg, 0.08))
        return clamp_arena((me[0] + L * math.cos(best_th), me[1] + L * math.sin(best_th)), 0.05)

    # ------------------------------------------------------------------ controle
    def drive(self, me, target):
        dx, dy = target[0] - me[0], target[1] - me[1]
        d = math.hypot(dx, dy)
        if d < STOP_DIST:
            return 0.0, 0.0
        e = wrap_angle(math.atan2(dy, dx) - me[2])
        if self.reverse and abs(e) < math.pi / 2 - REV_HYST:
            self.reverse = False
        elif not self.reverse and abs(e) > math.pi / 2 + REV_HYST:
            self.reverse = True
        direction = 1.0
        if self.reverse:
            e = wrap_angle(e - math.pi)
            direction = -1.0
        w = clamp(K_W * e, -W_MAX, W_MAX)
        v = direction * min(K_V * d, V_MAX) * max(0.0, math.cos(e))
        return clamp(v, -V_MAX, V_MAX), w

    def unstick(self, me, v, w, now):
        if self.game_paused(now):  # robôs congelados pelo juiz: não é encalhe
            self.stuck_ref = None
            self.recover_until = 0.0
            return v, w
        if now < self.recover_until:
            return -0.15 * self.recover_dir, 2.5
        if abs(v) < STUCK_V:
            self.stuck_ref = None
            return v, w
        if self.stuck_ref is None or dist(me, self.stuck_ref) > STUCK_MOVE:
            self.stuck_ref = (me[0], me[1], now)
        elif now - self.stuck_ref[2] > STUCK_T:
            rospy.loginfo("hero_%d: travado, manobrando", self.robot)
            self.recover_until = now + RECOVER_T
            self.recover_dir = 1.0 if v > 0 else -1.0
            self.stuck_ref = None
            return -0.15 * self.recover_dir, 2.5
        return v, w

    # ------------------------------------------------------------------ laço
    def run(self):
        rate = rospy.Rate(20)
        while not rospy.is_shutdown():
            if (self.me is None or len(self.opp) < len(self.opponents)
                    or self.enemy_flag is None or self.own_flag is None):
                rospy.logwarn_throttle(2.0, "waiting for odometry and flags (TODO 1)")
            else:
                try:
                    v, w = self.compute_command(self.me, list(self.opp.values()), self.enemy_flag,
                                                self.own_flag, self.carrying)
                except Exception as exc:  # nunca derruba o nó durante a partida
                    rospy.logerr_throttle(2.0, "ctf: erro no controle: %r" % (exc,))
                    v, w = 0.0, 0.0
                cmd = Twist()
                cmd.linear.x, cmd.angular.z = v, w
                self.pub.publish(cmd)
            try:
                rate.sleep()
            except rospy.ROSInterruptException:
                break


if __name__ == "__main__":
    CaptureTheFlag().run()
