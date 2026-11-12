#!/usr/bin/env python3
"""Registro de uma partida de rouba-bandeira (não faz parte do código da competição).

Roda no container ROS, ao lado de um cenário ctf em execução, e grava em --out:
  <nome>_amostras.csv  estado a 5 Hz (placar, poses, bandeiras, quem está segurado/carregando)
  <nome>_eventos.csv   eventos: ponto, captura (segurou), pegou/perdeu a bandeira, nova rodada
  <nome>.json          resumo da partida
e acrescenta uma linha em resumo.csv (na mesma pasta), uma por partida.

O tempo de jogo é somado a partir do round_time de /game/state (tempo do simulador, que pode
andar mais devagar que o relógio quando a renderização é por software). Sem round_time, usa o
relógio. A partida termina depois de --minutes minutos de jogo.

Uso (o rodar_partidas.sh já faz isso):
  ./run.sh shell
  python3 /ws/psr_exercicios/ctf/ctf_logger.py --minutes 5 --label teste --blue ctf.py --red none
"""
import argparse
import csv
import json
import os
import re
import time

import rospy
from geometry_msgs.msg import PointStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import Bool, String

from psr_hero.utils import pose_from_odom


def parse_score(obj):
    """(azul, vermelho) a partir do campo score, em dict ou lista."""
    if isinstance(obj, dict):
        low = {str(k).lower(): v for k, v in obj.items()}
        b, r = low.get("blue"), low.get("red")
        if isinstance(b, (int, float)) and isinstance(r, (int, float)):
            return int(b), int(r)
    if isinstance(obj, (list, tuple)) and len(obj) == 2 and all(isinstance(v, (int, float)) for v in obj):
        return int(obj[0]), int(obj[1])
    return None


def ids_of(obj):
    ids = set()
    if isinstance(obj, dict):
        obj = [k for k, v in obj.items() if v not in (False, 0, None, "", [])]
    if isinstance(obj, (list, tuple)):
        if obj and all(isinstance(v, bool) for v in obj):
            return {i for i, v in enumerate(obj) if v}
        for it in obj:
            if isinstance(it, bool):
                continue
            if isinstance(it, (int, float)):
                ids.add(int(it))
            elif isinstance(it, str) and re.findall(r"\d+", it):
                ids.add(int(re.findall(r"\d+", it)[-1]))
    elif isinstance(obj, (int, str)) and not isinstance(obj, bool):
        return ids_of([obj])
    return ids


class Logger(object):
    def __init__(self, a):
        self.a = a
        self.n = a.robots
        self.team = {k: ("blue" if (k < self.n // 2) else "red") for k in range(self.n)}
        self.pose = {}
        self.has_flag = {}
        self.flags = {}
        self.state = {}
        self.score0 = None
        self.score = (0, 0)
        self.held = set()
        self.rt_last = None
        self.game_t = 0.0
        self.wall0 = None
        self.resets = 0
        self.draws = 0
        self.counts = {"pontos_azul": 0, "pontos_vermelho": 0, "capturas_por_azul": 0,
                       "capturas_por_vermelho": 0, "pegou_bandeira_azul": 0,
                       "pegou_bandeira_vermelho": 0, "perdeu_bandeira_azul": 0,
                       "perdeu_bandeira_vermelho": 0}
        os.makedirs(a.out, exist_ok=True)
        base = os.path.join(a.out, a.label)
        self.f_s = open(base + "_amostras.csv", "w", newline="")
        self.f_e = open(base + "_eventos.csv", "w", newline="")
        self.w_s = csv.writer(self.f_s)
        self.w_e = csv.writer(self.f_e)
        cols = ["t_relogio", "t_jogo", "round_time", "placar_azul", "placar_vermelho", "segurados",
                "carregando"]
        for k in range(self.n):
            cols += ["hero_%d_x" % k, "hero_%d_y" % k]
        cols += ["flag_blue_x", "flag_blue_y", "flag_red_x", "flag_red_y"]
        self.w_s.writerow(cols)
        self.w_e.writerow(["t_relogio", "t_jogo", "evento", "detalhe"])

        for k in range(self.n):
            rospy.Subscriber("/hero_%d/odom" % k, Odometry, self.on_odom, callback_args=k, queue_size=1)
            rospy.Subscriber("/hero_%d/has_flag" % k, Bool, self.on_has, callback_args=k, queue_size=5)
        for c in ("blue", "red"):
            rospy.Subscriber("/flag/%s" % c, PointStamped, self.on_flag, callback_args=c, queue_size=1)
        rospy.Subscriber("/game/state", String, self.on_state, queue_size=10)

    def now(self):
        return time.time() - (self.wall0 or time.time())

    def event(self, kind, detail=""):
        self.w_e.writerow(["%.2f" % self.now(), "%.2f" % self.game_t, kind, detail])
        self.f_e.flush()
        rospy.loginfo("[%.1f s de jogo] %s %s", self.game_t, kind, detail)

    def on_odom(self, msg, k):
        self.pose[k] = pose_from_odom(msg)

    def on_flag(self, msg, c):
        self.flags[c] = (msg.point.x, msg.point.y)

    def on_has(self, msg, k):
        old = self.has_flag.get(k, False)
        self.has_flag[k] = msg.data
        if msg.data and not old:
            self.counts["pegou_bandeira_" + ("azul" if self.team[k] == "blue" else "vermelho")] += 1
            self.event("pegou_bandeira", "hero_%d" % k)
        elif old and not msg.data:
            self.event("largou_bandeira", "hero_%d" % k)

    def on_state(self, msg):
        try:
            st = json.loads(msg.data)
        except ValueError:
            return
        if not isinstance(st, dict):
            return
        if self.wall0 is None:
            self.wall0 = time.time()
            self.event("inicio", msg.data)
        self.state = st
        # tempo de jogo a partir do round_time
        rt = st.get("round_time")
        if isinstance(rt, (int, float)):
            if self.rt_last is not None:
                d = rt - self.rt_last
                if abs(d) < 1.0:
                    self.game_t += abs(d)
                else:
                    self.resets += 1
                    if max(self.rt_last, rt) >= 85.0:  # rodada chegou aos 90 s sem ponto
                        self.draws += 1
                        self.event("empate_90s", "round_time %.1f -> %.1f" % (self.rt_last, rt))
                    else:
                        self.event("nova_rodada", "round_time %.1f -> %.1f" % (self.rt_last, rt))
            self.rt_last = rt
        else:
            self.game_t = self.now()
        # placar
        sc = parse_score(st.get("score"))
        if sc is not None:
            if self.score0 is None:
                self.score0 = sc
                self.score = sc
            if sc != self.score:
                if sc[0] > self.score[0]:
                    self.counts["pontos_azul"] += sc[0] - self.score[0]
                    self.event("ponto", "azul %d x %d vermelho" % (sc[0] - self.score0[0], sc[1] - self.score0[1]))
                if sc[1] > self.score[1]:
                    self.counts["pontos_vermelho"] += sc[1] - self.score[1]
                    self.event("ponto", "vermelho %d x %d azul" % (sc[1] - self.score0[1], sc[0] - self.score0[0]))
                self.score = sc
        # capturas
        held = ids_of(st.get("held"))
        for k in held - self.held:
            by = "vermelho" if self.team.get(k) == "blue" else "azul"
            self.counts["capturas_por_" + by] += 1
            flag_lost = self.has_flag.get(k, False)
            if flag_lost:
                self.counts["perdeu_bandeira_" + ("azul" if self.team.get(k) == "blue" else "vermelho")] += 1
            self.event("segurado", "hero_%d%s" % (k, " (com a bandeira)" if flag_lost else ""))
        for k in self.held - held:
            self.event("solto", "hero_%d" % k)
        self.held = held

    def sample(self):
        sc0 = self.score0 or (0, 0)
        row = ["%.2f" % self.now(), "%.2f" % self.game_t, self.state.get("round_time", ""),
               self.score[0] - sc0[0], self.score[1] - sc0[1],
               " ".join("hero_%d" % k for k in sorted(self.held)),
               " ".join("hero_%d" % k for k, v in sorted(self.has_flag.items()) if v)]
        for k in range(self.n):
            p = self.pose.get(k)
            row += ["%.3f" % p[0], "%.3f" % p[1]] if p else ["", ""]
        for c in ("blue", "red"):
            f = self.flags.get(c)
            row += ["%.3f" % f[0], "%.3f" % f[1]] if f else ["", ""]
        self.w_s.writerow(row)

    def finish(self, reason):
        sc0 = self.score0 or (0, 0)
        b, r = self.score[0] - sc0[0], self.score[1] - sc0[1]
        draws = self.draws
        summary = dict(partida=self.a.label, azul=self.a.blue, vermelho=self.a.red,
                       placar_azul=b, placar_vermelho=r, empates_90s=draws,
                       tempo_jogo_s=round(self.game_t, 1), tempo_relogio_s=round(self.now(), 1),
                       fim=reason, ultimo_estado=self.state)
        summary.update(self.counts)
        self.event("fim", "%s: azul %d x %d vermelho" % (reason, b, r))
        with open(os.path.join(self.a.out, self.a.label + ".json"), "w") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        res = os.path.join(self.a.out, "resumo.csv")
        cols = ["partida", "azul", "vermelho", "placar_azul", "placar_vermelho", "empates_90s",
                "capturas_por_azul", "capturas_por_vermelho", "pegou_bandeira_azul",
                "pegou_bandeira_vermelho", "perdeu_bandeira_azul", "perdeu_bandeira_vermelho",
                "tempo_jogo_s", "tempo_relogio_s", "fim"]
        new = not os.path.exists(res)
        with open(res, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(cols)
            w.writerow([summary[c] for c in cols])
        self.f_s.close()
        self.f_e.close()
        print("RESULTADO %s: azul (%s) %d x %d vermelho (%s)" % (self.a.label, self.a.blue, b, r, self.a.red))

    def run(self):
        rate = rospy.Rate(5)
        limit = self.a.minutes * 60.0
        t_start = time.time()
        reason = "interrompida"
        try:
            while not rospy.is_shutdown():
                if self.wall0 is None:
                    if time.time() - t_start > 60:
                        rospy.logerr("sem /game/state há 60 s: o cenário ctf está rodando?")
                        reason = "sem_dados"
                        break
                else:
                    self.sample()
                    if self.game_t >= limit:
                        reason = "tempo"
                        break
                    if self.now() > limit * self.a.max_wall_factor:
                        reason = "tempo_relogio_esgotado"
                        break
                rate.sleep()
        except (KeyboardInterrupt, rospy.ROSInterruptException):
            pass
        self.finish(reason)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--minutes", type=float, default=5.0, help="duração da partida (tempo de jogo)")
    p.add_argument("--robots", type=int, default=4)
    p.add_argument("--label", default=time.strftime("partida_%H%M%S"))
    p.add_argument("--blue", default="?", help="arquivo do time azul (só para o registro)")
    p.add_argument("--red", default="?", help="arquivo do time vermelho (só para o registro)")
    p.add_argument("--out", default="/ws/psr_exercicios/ctf/partidas")
    p.add_argument("--max-wall-factor", type=float, default=4.0,
                   help="para também quando o relógio passar deste múltiplo da duração")
    a = p.parse_args(rospy.myargv()[1:])
    rospy.init_node("ctf_logger", anonymous=True, disable_signals=True)
    Logger(a).run()


if __name__ == "__main__":
    main()
