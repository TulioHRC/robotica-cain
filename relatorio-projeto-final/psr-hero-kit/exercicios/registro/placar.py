#!/usr/bin/env python3
import csv
import json
import os
import time

import rospy
from geometry_msgs.msg import PointStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import String

from psr_hero.utils import pose_from_odom

PASTA = os.path.dirname(os.path.abspath(__file__))
CHAVES = {"sumo": ("wins", "draws"), "ctf": ("score", "tags", "held", "carrying"), "soccer": ("blue", "red")}
INTERVALO = 0.2
ODOMETRIAS = {"hero_%d" % i: "/hero_%d/odom" % i for i in range(6)}
ODOMETRIAS["ball"] = "/ball/odom"
BANDEIRAS = {"flag_blue": "/flag/blue", "flag_red": "/flag/red"}


def nome_curto(script):
    return os.path.splitext(os.path.basename(str(script)))[0]


class Placar:
    def __init__(self):
        rospy.init_node("placar")
        self.jogo = rospy.get_param("~jogo", "soccer")
        if self.jogo not in CHAVES:
            raise SystemExit("jogo deve ser sumo, ctf ou soccer")
        padrao = self.jogo + ".py"
        self.time0 = rospy.get_param("~time0", padrao)
        self.time1 = rospy.get_param("~time1", padrao)
        self.duracao = float(rospy.get_param("~duracao", 300.0))
        self.rodadas = int(rospy.get_param("~rodadas", 20))
        pasta = os.path.join(PASTA, "logs")
        os.makedirs(pasta, exist_ok=True)
        nome = "%s_%s_x_%s_%s.csv" % (self.jogo, nome_curto(self.time0), nome_curto(self.time1),
                                      time.strftime("%Y%m%d-%H%M%S"))
        self.caminho = os.path.join(pasta, nome)
        self.arquivo = open(self.caminho, "w", newline="")
        self.escritor = csv.writer(self.arquivo, lineterminator="\n")
        self.escritor.writerow(["t", "estado", "poses"])
        self.dono(pasta)
        self.dono(self.caminho)
        self.t0 = None
        self.inicio = None
        self.ultima_chave = None
        self.ultimo_t = None
        self.fim = False
        self.poses = dict.fromkeys(list(ODOMETRIAS) + list(BANDEIRAS))
        for nome, topico in ODOMETRIAS.items():
            rospy.Subscriber(topico, Odometry, self.on_odom, callback_args=nome, queue_size=1)
        for nome, topico in BANDEIRAS.items():
            rospy.Subscriber(topico, PointStamped, self.on_flag, callback_args=nome, queue_size=1)
        rospy.Subscriber("/game/state", String, self.on_state, queue_size=50)
        rospy.loginfo("registrando %s: %s x %s em %s", self.jogo, self.time0, self.time1, self.caminho)

    def dono(self, caminho):
        st = os.stat(PASTA)
        try:
            os.chown(caminho, st.st_uid, st.st_gid)
        except OSError:
            pass

    def on_odom(self, msg, nome):
        self.poses[nome] = [round(v, 3) for v in pose_from_odom(msg)]

    def on_flag(self, msg, nome):
        self.poses[nome] = [round(msg.point.x, 3), round(msg.point.y, 3)]

    def rodadas_jogadas(self, estado):
        total = sum(estado["wins"]) + estado["draws"]
        return total - sum(self.inicio["wins"]) - self.inicio["draws"]

    def on_state(self, msg):
        if self.fim:
            return
        estado = json.loads(msg.data)
        t = estado.get("t")
        if t is None:
            return
        if self.t0 is None:
            self.t0 = t
            self.inicio = estado
        chave = json.dumps([estado.get(k) for k in CHAVES[self.jogo]])
        if chave != self.ultima_chave or t - self.ultimo_t >= INTERVALO:
            poses = {k: v for k, v in self.poses.items() if v is not None}
            self.escritor.writerow(["%.2f" % (t - self.t0), json.dumps(estado, separators=(",", ":")),
                                    json.dumps(poses, separators=(",", ":"))])
            self.ultima_chave = chave
            self.ultimo_t = t
        if self.jogo == "sumo":
            acabou = self.rodadas_jogadas(estado) >= self.rodadas
        else:
            acabou = t - self.t0 >= self.duracao
        if acabou:
            self.fim = True
            self.arquivo.close()
            rospy.loginfo("partida concluída: %s", self.caminho)
            rospy.signal_shutdown("fim da partida")


if __name__ == "__main__":
    placar = Placar()
    rospy.on_shutdown(lambda: placar.arquivo.close())
    rospy.spin()