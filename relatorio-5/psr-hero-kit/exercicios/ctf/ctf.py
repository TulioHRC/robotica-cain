#!/usr/bin/env python3
"""Capture the flag (student template). One file drives every robot of your team.

The arena is 1.6 x 1.6 m, split at x = 0. Blue (base on the left, x = -0.62 m) has
hero_0 and hero_1; red (base on the right, x = +0.62 m) has hero_2 and hero_3.
(With two robots: hero_0 is blue and hero_1 is red.) In a team of two, one robot
is the attacker and the other the defender (parameter ~role): the attacker tries to
steal the flag while the defender blocks.

Rules
  * Touch the enemy flag (< 0.07 m) and you carry it. It follows you.
  * Carry it into your base circle (radius 0.14 m around your flag) to score a point.
  * Inside YOUR half, touching an opponent (< 0.10 m) HOLDS it still for 4 s (its commands
    are ignored; the game goes on for everybody else). If it was carrying your flag, the
    flag returns to your base. A held robot cannot hold others, and after the release it
    is immune for 1.5 s.
  * In the opponents' half you are the one who can be held: block one opponent while
    your teammate goes for the flag.
  * 90 s without a point is a draw and everyone goes back to the start.

Topics
  /hero_N/odom        nav_msgs/Odometry          pose of every robot
  /hero_N/has_flag    std_msgs/Bool              robot N carries the enemy flag
  /flag/blue          geometry_msgs/PointStamped position of the blue flag
  /flag/red           geometry_msgs/PointStamped position of the red flag
  /hero_N/laser       sensor_msgs/LaserScan      the 8-beam lidar also sees the other robots
  /hero_N/cmd_vel     geometry_msgs/Twist        your command

Parameters: ~robot (your id), ~team ('blue' or 'red'), ~role ('attacker' or 'defender'),
~opponents (list of ids). The launch file fills them in.

Run:  ./run.sh run ctf      (see README.md in this folder)
"""
import math  # noqa: F401

import rospy
from geometry_msgs.msg import PointStamped, Twist  # noqa: F401
from nav_msgs.msg import Odometry  # noqa: F401
from std_msgs.msg import Bool  # noqa: F401

from psr_hero.utils import V_MAX, W_MAX, clamp, pose_from_odom, wrap_angle  # noqa: F401

BASE_X = 0.62  # m, blue at -BASE_X, red at +BASE_X
BASE_RADIUS = 0.14  # m


class CaptureTheFlag:
    def __init__(self):
        rospy.init_node("ctf")
        self.robot = rospy.get_param("~robot", 0)
        self.team = rospy.get_param("~team", "blue" if self.robot == 0 else "red")
        self.role = rospy.get_param("~role", "attacker")
        self.opponents = list(rospy.get_param("~opponents", [1 if self.robot == 0 else 0]))
        self.blue = self.team == "blue"
        self.home = (-BASE_X if self.blue else BASE_X, 0.0)  # your base and your flag
        self.me = None  # (x, y, yaw)
        self.opp = {}  # opponent id -> (x, y, yaw)
        self.enemy_flag = None  # (x, y)
        self.own_flag = None  # (x, y): away from self.home means an opponent has it
        self.carrying = False  # True while you hold the enemy flag

        # Ready: the publisher for the velocity command.
        self.pub = rospy.Publisher("/hero_%d/cmd_vel" % self.robot, Twist, queue_size=1)

        # TODO 1 (ROS): subscribe to
        #   /hero_<robot>/odom                       -> self.on_me
        #   /hero_<k>/odom for k in self.opponents   -> self.on_opp (pass k as callback_args)
        #   the enemy flag topic (/flag/red if you are blue, /flag/blue if red) -> self.on_enemy_flag
        #   your own flag topic                      -> self.on_own_flag
        #   /hero_<robot>/has_flag                   -> self.on_has_flag

    def on_me(self, msg):
        # TODO 1 (ROS): self.me = pose_from_odom(msg)
        pass

    def on_opp(self, msg, k):
        # TODO 1 (ROS): self.opp[k] = pose_from_odom(msg)
        pass

    def on_enemy_flag(self, msg):
        # TODO 1 (ROS): self.enemy_flag = (msg.point.x, msg.point.y)
        pass

    def on_own_flag(self, msg):
        # TODO 1 (ROS): self.own_flag = (msg.point.x, msg.point.y)
        pass

    def on_has_flag(self, msg):
        # TODO 1 (ROS): self.carrying = msg.data
        pass

    def compute_command(self, me, opponents, enemy_flag, own_flag, carrying):
        """TODO 2: choose (linear_x, angular_z).

        me: (x, y, yaw). opponents: list of (x, y, yaw). flags: (x, y). carrying: you hold the enemy flag.
        self.role tells whether you attack (go for the flag, run home, avoid being tagged in the
        opponents' half) or defend (stay between your flag and the opponents, chase intruders).
        """
        return 0.0, 0.0

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
            rate.sleep()


if __name__ == "__main__":
    CaptureTheFlag().run()
