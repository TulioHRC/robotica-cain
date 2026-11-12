#!/usr/bin/env python3
"""Rouba-bandeira, versão 1 (baseline usada nas comparações).

Estratégia simples, sem desvio:
  Atacante: IR_BANDEIRA (vai reto até a bandeira inimiga) -> VOLTAR (vai reto até a base).
  Defensor: GUARDAR (fica entre a bandeira e o adversário mais próximo dela, a 0.22 m)
            ou PERSEGUIR (vai até o adversário mais próximo que entrar na nossa metade,
            sem antecipar o movimento e sem cruzar a linha do meio).
Controlador: ir até um ponto só de frente, w = K_W * e, v = min(K_V * d, V_MAX) * max(0, cos e).

Como na versão final, o time vermelho calcula tudo no mundo girado de 180°, para o
mesmo arquivo servir dos dois lados.
"""
import math

import rospy
from geometry_msgs.msg import PointStamped, Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Bool

from psr_hero.utils import V_MAX, W_MAX, clamp, pose_from_odom, wrap_angle

BASE_X = 0.62  # m, blue at -BASE_X, red at +BASE_X
BASE_RADIUS = 0.14  # m
HOME = (-BASE_X, 0.0)  # referencial do time
K_V = 1.5
K_W = 3.0
GUARD_R = 0.22
MID_SAFE = 0.04


class CaptureTheFlag:
    def __init__(self):
        rospy.init_node("ctf")
        self.robot = rospy.get_param("~robot", 0)
        self.team = rospy.get_param("~team", "blue" if self.robot == 0 else "red")
        self.role = rospy.get_param("~role", "attacker")
        self.opponents = list(rospy.get_param("~opponents", [1 if self.robot == 0 else 0]))
        self.blue = self.team == "blue"
        self.home = (-BASE_X if self.blue else BASE_X, 0.0)
        self.me = None
        self.opp = {}
        self.enemy_flag = None
        self.own_flag = None
        self.carrying = False

        self.pub = rospy.Publisher("/hero_%d/cmd_vel" % self.robot, Twist, queue_size=1)

        rospy.Subscriber("/hero_%d/odom" % self.robot, Odometry, self.on_me, queue_size=1)
        for k in self.opponents:
            rospy.Subscriber("/hero_%d/odom" % k, Odometry, self.on_opp, callback_args=k, queue_size=1)
        enemy, own = ("red", "blue") if self.blue else ("blue", "red")
        rospy.Subscriber("/flag/%s" % enemy, PointStamped, self.on_enemy_flag, queue_size=1)
        rospy.Subscriber("/flag/%s" % own, PointStamped, self.on_own_flag, queue_size=1)
        rospy.Subscriber("/hero_%d/has_flag" % self.robot, Bool, self.on_has_flag, queue_size=1)

    def on_me(self, msg):
        self.me = pose_from_odom(msg)

    def on_opp(self, msg, k):
        self.opp[k] = pose_from_odom(msg)

    def on_enemy_flag(self, msg):
        self.enemy_flag = (msg.point.x, msg.point.y)

    def on_own_flag(self, msg):
        self.own_flag = (msg.point.x, msg.point.y)

    def on_has_flag(self, msg):
        self.carrying = msg.data

    def to_team(self, x, y, yaw=0.0):
        if self.blue:
            return (x, y, yaw)
        return (-x, -y, wrap_angle(yaw + math.pi))

    def go_to(self, me, target):
        dx, dy = target[0] - me[0], target[1] - me[1]
        d = math.hypot(dx, dy)
        if d < 0.015:
            return 0.0, 0.0
        e = wrap_angle(math.atan2(dy, dx) - me[2])
        w = clamp(K_W * e, -W_MAX, W_MAX)
        v = min(K_V * d, V_MAX) * max(0.0, math.cos(e))
        return v, w

    def compute_command(self, me, opponents, enemy_flag, own_flag, carrying):
        me = self.to_team(*me)
        ef = self.to_team(*enemy_flag)[:2]
        opps = [self.to_team(*o)[:2] for o in opponents]
        if self.role != "defender":
            return self.go_to(me, HOME if carrying else ef)
        intruders = [o for o in opps if o[0] < -0.02]
        if intruders:
            o = min(intruders, key=lambda q: math.hypot(q[0] - me[0], q[1] - me[1]))
            return self.go_to(me, (min(o[0], -MID_SAFE), o[1]))
        ref = min(opps, key=lambda q: math.hypot(q[0] - HOME[0], q[1] - HOME[1])) if opps else (0.0, 0.0)
        dx, dy = ref[0] - HOME[0], ref[1] - HOME[1]
        n = math.hypot(dx, dy) or 1.0
        p = (min(HOME[0] + GUARD_R * dx / n, -MID_SAFE - 0.05), HOME[1] + GUARD_R * dy / n)
        return self.go_to(me, p)

    def run(self):
        rate = rospy.Rate(20)
        while not rospy.is_shutdown():
            if (self.me is None or len(self.opp) < len(self.opponents)
                    or self.enemy_flag is None or self.own_flag is None):
                rospy.logwarn_throttle(2.0, "waiting for odometry and flags (TODO 1)")
            else:
                v, w = self.compute_command(self.me, list(self.opp.values()), self.enemy_flag,
                                            self.own_flag, self.carrying)
                cmd = Twist()
                cmd.linear.x, cmd.angular.z = v, w
                self.pub.publish(cmd)
            try:
                rate.sleep()
            except rospy.ROSInterruptException:
                break


if __name__ == "__main__":
    CaptureTheFlag().run()
