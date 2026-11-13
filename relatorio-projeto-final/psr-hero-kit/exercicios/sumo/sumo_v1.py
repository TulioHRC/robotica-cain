#!/usr/bin/env python3
# Sumô - estratégia: MIRA PARA A BORDA (empurra o adversário para a borda mais próxima dele)
import math

import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

from psr_hero.utils import V_MAX, W_MAX, clamp, pose_from_odom, wrap_angle

RING_RADIUS = 0.40
ROBOT_RADIUS = 0.037

K_ANG = 8.0  # ganho P do rumo (rad/s por rad)
# Anda a V_MAX até ALINHADO de erro: o simulador limita a força a 0,2 N por eixo, e
# até ~70° de erro o empurrão continua saturado; reduzir só daria força ao adversário.
ALINHADO = 1.2  # rad
CONTATO = 2 * ROBOT_RADIUS + 0.015  # m entre centros: consideramos que há contato
R_PERIGO = 0.28  # m do centro: em contato e sendo empurrado para fora, desvia
T_DESVIO = 0.6  # s de duração do desvio
ANG_DESVIO = 1.0  # rad somados ao rumo durante o desvio
R_VOLTA = 0.30  # m do centro: sem contato, volta para o centro
R_VOLTA_FIM = 0.20  # histerese: para de voltar aqui
AVANCO_BORDA = 0.6  # 0..1: quanto a mira puxa para a borda mais próxima do adversário
BORDA_NO_CONTATO = 0.0  # 1: mantém a mira deslocada também durante o contato
DT_NOMINAL = 0.05  # s, período do laço (20 Hz)
SALTO_TELEPORTE = 0.05  # m em um ciclo: andando é no máximo 1 cm, então é rodada nova


class Sumo:
    def __init__(self):
        rospy.init_node("sumo")
        self.robot = rospy.get_param("~robot", 0)
        self.opponent = rospy.get_param("~opponent", 1)
        self.me = None
        self.speed = 0.0
        self.opp = None

        self.estado = "ATACAR"
        self.ultimo = None
        self.t_desvio = -1.0
        self.lado_desvio = 1.0

        self.pub = rospy.Publisher("/hero_%d/cmd_vel" % self.robot, Twist, queue_size=1)
        rospy.Subscriber("/hero_%d/odom" % self.robot, Odometry, self.on_me, queue_size=1)
        rospy.Subscriber("/hero_%d/odom" % self.opponent, Odometry, self.on_opp, queue_size=1)

    def on_me(self, msg):
        self.me = pose_from_odom(msg)
        self.speed = msg.twist.twist.linear.x

    def on_opp(self, msg):
        self.opp = pose_from_odom(msg)

    @staticmethod
    def rumo(alvo_ang, me):
        # com erro grande gira parado: uma curva larga levaria o robô para fora do ringue
        erro = wrap_angle(alvo_ang - me[2])
        w = clamp(K_ANG * erro, -W_MAX, W_MAX)
        v = V_MAX if abs(erro) < ALINHADO else 0.0
        return v, w

    def compute_command(self, me, opp, speed, now):
        r_me = math.hypot(me[0], me[1])
        dx, dy = opp[0] - me[0], opp[1] - me[1]
        n = math.atan2(dy, dx)  # direção da linha de centros (nós -> adversário)
        em_contato = math.hypot(dx, dy) < CONTATO

        # velocidade radial (> 0: indo para fora); um salto grande é o teleporte do juiz
        vr = 0.0
        if self.ultimo is not None:
            (x0, y0, _), t0 = self.ultimo
            dt = now - t0
            if math.hypot(me[0] - x0, me[1] - y0) > SALTO_TELEPORTE:
                self.estado, self.t_desvio = "ATACAR", -1.0
            elif r_me > 1e-3 and dt > 1e-3:
                vr = ((me[0] - x0) * me[0] + (me[1] - y0) * me[1]) / (r_me * max(dt, DT_NOMINAL))
        self.ultimo = (me, now)

        # Só desvia se o adversário está do lado de dentro (entre nós e o centro).
        # Se ele está do lado de fora, somos nós que o empurramos para a borda, e
        # desviar ali faria o robô cair sozinho.
        adv_dentro = dx * me[0] + dy * me[1] < 0.0
        if now < self.t_desvio:
            self.estado = "DESVIAR"
        elif em_contato and adv_dentro and r_me > R_PERIGO and vr > 0.0:
            # gira para o lado em que o contato escorrega mais fácil
            cruz = me[0] * dy - me[1] * dx
            self.lado_desvio = -1.0 if cruz > 0 else 1.0
            self.t_desvio = now + T_DESVIO
            self.estado = "DESVIAR"
        elif self.estado == "DESVIAR":
            self.estado = "ATACAR"

        if self.estado != "DESVIAR":
            if not em_contato and r_me > R_VOLTA:
                self.estado = "VOLTAR"
            elif self.estado == "VOLTAR" and (em_contato or r_me < R_VOLTA_FIM):
                self.estado = "ATACAR"

        if self.estado == "DESVIAR":
            return self.rumo(n + self.lado_desvio * ANG_DESVIO, me)
        if self.estado == "VOLTAR":
            return self.rumo(math.atan2(-me[1], -me[0]), me)
        return self.rumo(self.mira_borda(me, opp, n, em_contato), me)

    @staticmethod
    def mira_borda(me, opp, n, em_contato):
        # Soma à direção do adversário um pedaço da direção radial dele (centro ->
        # adversário): o contato acontece pelo lado de dentro e o empurrão sai para a
        # borda mais próxima dele. Com AVANCO_BORDA < 1 a mira nunca se afasta dele.
        ro = math.hypot(opp[0], opp[1])
        if AVANCO_BORDA <= 0.0 or ro < 1e-3 or (em_contato and not BORDA_NO_CONTATO):
            return n
        ax = math.cos(n) + AVANCO_BORDA * opp[0] / ro
        ay = math.sin(n) + AVANCO_BORDA * opp[1] / ro
        return math.atan2(ay, ax)

    def run(self):
        rate = rospy.Rate(20)
        while not rospy.is_shutdown():
            if self.me is None or self.opp is None:
                rospy.logwarn_throttle(2.0, "waiting for odometry")
            else:
                v, w = self.compute_command(self.me, self.opp, self.speed, rospy.get_time())
                cmd = Twist()
                cmd.linear.x, cmd.angular.z = v, w
                self.pub.publish(cmd)
            rate.sleep()


if __name__ == "__main__":
    Sumo().run()
