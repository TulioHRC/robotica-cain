#!/usr/bin/env python3
"""Go-to-goal navigation (student template).

Goal: drive the robot to the goal point, then to the next one the simulator
draws, as many times as possible. A goal counts when the robot centre gets
within 6 cm of it.

Topics:
  /hero_N/odom   nav_msgs/Odometry         pose in the 'world' frame (x, y, yaw)
  /hero_N/goal   geometry_msgs/PointStamped  current goal (world frame)
  /hero_N/cmd_vel  geometry_msgs/Twist      what you publish (linear.x, angular.z)

Run:  ./run.sh run goto      (see README.md in this folder)
"""
import csv
import json
import math  # noqa: F401
import os
import time

import rospy
from geometry_msgs.msg import PointStamped, Twist  # noqa: F401
from nav_msgs.msg import Odometry  # noqa: F401
from std_msgs.msg import String

from psr_hero.utils import V_MAX, W_MAX, clamp, pose_from_odom, wrap_angle  # noqa: F401

PASTA = os.path.dirname(os.path.abspath(__file__))
COLUNAS = ["t", "x", "y", "theta", "xg", "yg", "rho", "alpha", "v", "w", "metas"]


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


class Goto:
    CONFIG = "A"
    K_ALPHA = 3.0
    K_RHO = 1.5
    V_LIN = 0.20
    W_LIM = 4.0
    DURACAO = 180.0

    def __init__(self):
        rospy.init_node("goto")
        self.robot = rospy.get_param("~robot", 0)
        self.pose = None  # (x, y, yaw)
        self.goal = None  # (x, y)
        self.t_sim = None
        self.metas = -1

        # Ready: the publisher for the velocity command.
        self.pub = rospy.Publisher("/hero_%d/cmd_vel" % self.robot, Twist, queue_size=1)

        # TODO 1 (ROS): subscribe to /hero_<robot>/odom (Odometry) -> self.on_odom
        #               and to /hero_<robot>/goal (PointStamped) -> self.on_goal.
        rospy.Subscriber("/hero_%d/odom" % self.robot, Odometry, self.on_odom, queue_size=1)
        rospy.Subscriber("/hero_%d/goal" % self.robot, PointStamped, self.on_goal, queue_size=1)
        rospy.Subscriber("/game/state", String, self.on_state, queue_size=1)

    def on_odom(self, msg):
        # TODO 1 (ROS): store the pose. pose_from_odom(msg) returns (x, y, yaw).
        self.pose = pose_from_odom(msg)

    def on_goal(self, msg):
        # TODO 1 (ROS): store the goal point (msg.point.x, msg.point.y).
        self.goal = (msg.point.x, msg.point.y)

    def on_state(self, msg):
        dados = json.loads(msg.data)
        self.t_sim = dados.get("t")
        metas = dados.get("reached")
        if metas and self.robot < len(metas):
            self.metas = metas[self.robot]

    def erros(self, pose, goal):
        x, y, yaw = pose
        dx, dy = goal[0] - x, goal[1] - y
        return math.hypot(dx, dy), wrap_angle(math.atan2(dy, dx) - yaw)

    def compute_command(self, pose, goal):
        """TODO 2: a controller that drives the robot to the goal.

        pose: (x, y, yaw), goal: (x, y). Returns (linear_x, angular_z).
        Hint: compute the heading error (use wrap_angle), turn proportionally to
        it and move forward only when the robot is roughly pointing at the goal.
        """
        rho, alpha = self.erros(pose, goal)
        w = clamp(self.K_ALPHA * alpha, -self.W_LIM, self.W_LIM)
        v = clamp(self.K_RHO * rho, 0.0, self.V_LIN) * max(0.0, math.cos(alpha))
        return v, w

    def run(self):
        rate = rospy.Rate(20)
        registro = None
        t0 = None
        while not rospy.is_shutdown():
            if self.pose is None or self.goal is None:
                rospy.logwarn_throttle(2.0, "waiting for pose and goal (TODO 1)")
            else:
                v, w = self.compute_command(self.pose, self.goal)
                cmd = Twist()
                cmd.linear.x, cmd.angular.z = v, w
                self.pub.publish(cmd)
                if self.t_sim is not None:
                    if registro is None:
                        registro = Registro("goto_" + self.CONFIG, COLUNAS)
                        rospy.on_shutdown(registro.fechar)
                        t0 = self.t_sim
                        rospy.loginfo("ensaio %s iniciado: %s", self.CONFIG, registro.caminho)
                    t = self.t_sim - t0
                    x, y, theta = self.pose
                    rho, alpha = self.erros(self.pose, self.goal)
                    registro.escrever([t, x, y, theta, self.goal[0], self.goal[1], rho, alpha, v, w, self.metas])
                    if t >= self.DURACAO:
                        self.pub.publish(Twist())
                        registro.fechar()
                        rospy.loginfo("ensaio %s concluído: %s", self.CONFIG, registro.caminho)
                        rospy.signal_shutdown("fim do ensaio")
            rate.sleep()


if __name__ == "__main__":
    Goto().run()
