#!/usr/bin/env python3
# Sumô - estratégia: ÓRBITA (orbita no contato e golpeia quando está mais forte)
import math

import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

from psr_hero.utils import V_MAX, W_MAX, clamp, pose_from_odom, wrap_angle

R = 0.037  # m, raio do robô
K_ANG = 8.0  # ganho P do rumo (rad/s por rad)
ALINHADO = 1.2  # rad: com erro de rumo maior, gira parado em vez de andar
CONTATO = 2 * R + 0.015  # m entre centros: consideramos que há contato
ORB_ALFA = 25.0  # graus: desvio do rumo para orbitar no contato
ADV_MIN = 0.02  # N: vantagem estimada para golpear reto
T_GOLPE_MIN = 0.4  # s: mantém o golpe pelo menos isso
R_VOLTA = 0.30  # m do centro: sem contato, volta para o centro
R_PERIGO = 0.28  # m do centro: em contato e sendo empurrado para fora, desvia
T_DESVIO = 0.6  # s de duração do desvio
ANG_DESVIO = 1.0  # rad somados ao rumo durante o desvio


def forca(yaw, n):
    # O simulador limita a força do robô a 0,2 N em cada eixo do mundo. Empurrando
    # parado, cada componente é 3 * 0,2 * (cos, sin) do rumo, cortada em 0,2 N.
    # Projetada na direção n, dá a força útil: até 0,28 N na diagonal se alinhado.
    fx = clamp(0.6 * math.cos(yaw), -0.2, 0.2)
    fy = clamp(0.6 * math.sin(yaw), -0.2, 0.2)
    return fx * math.cos(n) + fy * math.sin(n)


class Sumo:
    def __init__(self):
        rospy.init_node("sumo")
        self.robot = rospy.get_param("~robot", 0)
        self.opponent = rospy.get_param("~opponent", 1)
        self.me = None
        self.speed = 0.0
        self.opp = None
        self.t_desvio = -1.0
        self.lado = 1.0
        self.ultimo = None
        self.t_golpe = -1.0
        self.pub = rospy.Publisher("/hero_%d/cmd_vel" % self.robot, Twist, queue_size=1)
        rospy.Subscriber("/hero_%d/odom" % self.robot, Odometry, self.on_me, queue_size=1)
        rospy.Subscriber("/hero_%d/odom" % self.opponent, Odometry, self.on_opp, queue_size=1)

    def on_me(self, msg):
        self.me = pose_from_odom(msg)
        self.speed = msg.twist.twist.linear.x

    def on_opp(self, msg):
        self.opp = pose_from_odom(msg)

    @staticmethod
    def rumo(ang, me):
        e = wrap_angle(ang - me[2])
        return (V_MAX if abs(e) < ALINHADO else 0.0), clamp(K_ANG * e, -W_MAX, W_MAX)

    def compute_command(self, me, opp, speed, now):
        # salto maior que 5 cm em um ciclo só acontece no teleporte do juiz: rodada nova
        if self.ultimo is not None and math.hypot(me[0] - self.ultimo[0], me[1] - self.ultimo[1]) > 0.05:
            self.t_desvio = -1.0
            self.t_golpe = -1.0
        # velocidade radial (> 0: indo para fora do ringue)
        vr = 0.0
        rme = math.hypot(me[0], me[1])
        if self.ultimo is not None and rme > 1e-3:
            vr = ((me[0] - self.ultimo[0]) * me[0] + (me[1] - self.ultimo[1]) * me[1]) / rme / 0.05
        self.ultimo = me
        dx, dy = opp[0] - me[0], opp[1] - me[1]
        n = math.atan2(dy, dx)  # direção da linha de centros (nós -> adversário)
        contato = math.hypot(dx, dy) < CONTATO
        dentro = dx * me[0] + dy * me[1] < 0  # adversário entre nós e o centro

        # Proteção de borda. Só desvia se o adversário está do lado de dentro e nos
        # leva para fora: girando para o lado, o contato escorrega e ele passa direto.
        if now < self.t_desvio:
            return self.rumo(n + self.lado * ANG_DESVIO, me)
        if contato and dentro and rme > R_PERIGO and vr > 0.0:
            cruz = me[0] * dy - me[1] * dx
            self.lado = -1.0 if cruz > 0 else 1.0
            self.t_desvio = now + T_DESVIO
            return self.rumo(n + self.lado * ANG_DESVIO, me)
        if not contato and rme > R_VOLTA:
            return self.rumo(math.atan2(-me[1], -me[0]), me)
        if not contato:
            return self.rumo(n, me)

        # GOLPE: empurra reto quando estamos mais fortes que ele ao longo da linha
        if now < self.t_golpe or forca(n, n) - forca(opp[2], n + math.pi) > ADV_MIN:
            if now >= self.t_golpe:
                self.t_golpe = now + T_GOLPE_MIN
            return self.rumo(n, me)
        # ORBITA: gira a linha de centros para a diagonal mais próxima, onde um
        # adversário com o rumo atrasado empurra com menos força que nós
        alvo = math.floor(n / (math.pi / 2)) * (math.pi / 2) + math.pi / 4
        e = wrap_angle(alvo - n)
        # andar para o lado -perpendicular gira n no sentido +
        return self.rumo(n - math.copysign(math.radians(ORB_ALFA), e), me)

    def run(self):
        rate = rospy.Rate(20)
        while not rospy.is_shutdown():
            if self.me is not None and self.opp is not None:
                v, w = self.compute_command(self.me, self.opp, self.speed, rospy.get_time())
                cmd = Twist()
                cmd.linear.x, cmd.angular.z = v, w
                self.pub.publish(cmd)
            rate.sleep()


if __name__ == "__main__":
    Sumo().run()
