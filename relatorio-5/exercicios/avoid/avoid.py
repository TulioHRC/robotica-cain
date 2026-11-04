#!/usr/bin/env python3
"""Obstacle avoidance with the 8-beam lidar (student template).

Goal: keep the robot moving in the arena without touching the obstacle in the
middle or the walls.

Lidar: /hero_N/laser (sensor_msgs/LaserScan), 8 beams, range 0.037 .. 0.5 m.
Beam k points at the angle -pi + k * pi/4 from the robot heading
(counter-clockwise positive), so beam 4 looks forward, beams 3 and 5 look 45
degrees to the right and to the left, and beam 0 looks backwards. A beam that
sees nothing reports 0.5. Distances are measured from the robot centre, so a
robot touching a wall reads about 0.037.

Run:  ./run.sh run avoid      (see README.md in this folder)
"""
import csv
import json
import os
import random
import time

import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan  # noqa: F401  (you will need it for TODO 1)
from std_msgs.msg import String

from psr_hero.utils import V_MAX, W_MAX, beam_angle, clamp  # noqa: F401
from psr_hero.utils import pose_from_odom

PASTA = os.path.dirname(os.path.abspath(__file__))
COLUNAS = ["t", "x", "y", "theta", "d_min"] + ["d%d" % k for k in range(8)] + ["v", "w", "escape"]


class Registro:
    def __init__(self, nome, colunas):
        pasta = os.path.join(PASTA, "logs")
        os.makedirs(pasta, exist_ok=True)
        self.caminho = os.path.join(pasta, "%s_%s.csv" % (nome, time.strftime("%Y%m%d-%H%M%S")))
        self.arquivo = open(self.caminho, "w", newline="")
        self.escritor = csv.writer(self.arquivo, lineterminator="\n")
        self.escritor.writerow(colunas)
        self.linhas = 0
        self.dono(pasta)
        self.dono(self.caminho)

    def dono(self, caminho):
        st = os.stat(PASTA)
        try:
            os.chown(caminho, st.st_uid, st.st_gid)
        except OSError:
            pass

    def escrever(self, linha):
        self.escritor.writerow(["%.4f" % x if isinstance(x, float) else x for x in linha])
        self.linhas += 1
        if self.linhas % 20 == 0:
            self.arquivo.flush()

    def fechar(self):
        if not self.arquivo.closed:
            self.arquivo.close()


class Avoid:
    CONFIG = "A"
    V_LIN = 0.15
    D_LENTO = 0.30
    D_PARE = 0.08
    K_W = 6.0
    W_LIM = 3.0
    W_ESC = 2.5
    D_GIRO = 0.13
    D_LIVRE = 0.20
    D_INF = 0.30
    W_VAG = 1.0
    T_VAG = 40
    SEMENTE = 1
    DURACAO = 300.0

    def __init__(self):
        rospy.init_node("avoid")
        self.robot = rospy.get_param("~robot", 0)
        self.scan = None
        self.pose = None
        self.t_sim = None
        self.escape = False
        self.s = 1
        self.rng = random.Random(self.SEMENTE)
        self.vies = 0.0
        self.k = 0

        # Ready: the publisher for the velocity command.
        self.pub = rospy.Publisher("/hero_%d/cmd_vel" % self.robot, Twist, queue_size=1)

        # TODO 1 (ROS): subscribe to the lidar topic of this robot
        #   (/hero_<robot>/laser, message type LaserScan) and call self.on_scan.
        rospy.Subscriber("/hero_%d/laser" % self.robot, LaserScan, self.on_scan, queue_size=1)
        rospy.Subscriber("/hero_%d/odom" % self.robot, Odometry, self.on_odom, queue_size=1)
        rospy.Subscriber("/game/state", String, self.on_state, queue_size=1)

    def on_scan(self, scan):
        # TODO 1 (ROS): keep the latest message in self.scan.
        self.scan = scan

    def on_odom(self, msg):
        self.pose = pose_from_odom(msg)

    def on_state(self, msg):
        self.t_sim = json.loads(msg.data).get("t")

    def compute_command(self, ranges):
        """TODO 2: turn the 8 lidar ranges into a velocity command.

        ranges: list with 8 floats (m). Returns (linear_x [m/s], angular_z [rad/s]).
        Linear speed is limited to V_MAX = 0.2 m/s and angular speed to W_MAX = 4 rad/s.
        Hint: the robot should keep moving, slow down when something is in front
        and turn away from the side where the obstacle is closer.
        """
        d = [min(r, self.D_INF) for r in ranges]
        d_f = min(d[3], d[4], d[5])
        d_e = (d[5] + d[6]) / 2.0
        d_d = (d[2] + d[3]) / 2.0
        f = (d_f - self.D_PARE) / (self.D_LENTO - self.D_PARE)
        v = self.V_LIN * clamp(f, 0.0, 1.0)
        if not self.escape and d_f < self.D_GIRO:
            self.escape = True
            self.s = 1 if d_e >= d_d else -1
        if self.escape:
            w = self.s * self.W_ESC
            self.escape = d_f <= self.D_LIVRE
        else:
            if self.k % self.T_VAG == 0:
                self.vies = self.rng.uniform(-self.W_VAG, self.W_VAG)
            self.k += 1
            w = self.K_W * (d_e - d_d) + self.vies
        return v, clamp(w, -self.W_LIM, self.W_LIM)

    def publish(self, v, w):
        cmd = Twist()
        cmd.linear.x = v
        cmd.angular.z = w
        self.pub.publish(cmd)

    def run(self):
        rate = rospy.Rate(20)
        registro = None
        t0 = None
        while not rospy.is_shutdown():
            if self.scan is None:
                rospy.logwarn_throttle(2.0, "no lidar data yet: is the subscriber of TODO 1 in place?")
            else:
                ranges = list(self.scan.ranges)
                v, w = self.compute_command(ranges)
                self.publish(v, w)
                if self.pose is not None and self.t_sim is not None:
                    if registro is None:
                        registro = Registro("avoid_" + self.CONFIG, COLUNAS)
                        rospy.on_shutdown(registro.fechar)
                        t0 = self.t_sim
                        rospy.loginfo("ensaio %s iniciado: %s", self.CONFIG, registro.caminho)
                    t = self.t_sim - t0
                    x, y, theta = self.pose
                    registro.escrever([t, x, y, theta, min(ranges)] + ranges + [v, w, int(self.escape)])
                    if t >= self.DURACAO:
                        self.publish(0.0, 0.0)
                        registro.fechar()
                        rospy.loginfo("ensaio %s concluído: %s", self.CONFIG, registro.caminho)
                        rospy.signal_shutdown("fim do ensaio")
            rate.sleep()


if __name__ == "__main__":
    Avoid().run()
