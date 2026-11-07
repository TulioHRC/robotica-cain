#!/usr/bin/env python3
"""Sumo (student template).

Push the other robot out of the circular ring (radius 0.40 m, centre (0, 0)).
A robot loses when its centre leaves the ring; a round ends in a draw after
40 s. There is no wall: use the odometry to know where you are.

Both robots have the same traction, so a head-on push is a stalemate. Think
about angles, timing and not leaving the ring yourself.

Topics:
  /hero_N/odom   nav_msgs/Odometry   pose of every robot
  /hero_N/laser  sensor_msgs/LaserScan   the 8-beam lidar also sees the opponent
  /hero_N/cmd_vel  geometry_msgs/Twist   your command

Run:  ./run.sh run sumo      (see README.md in this folder)
"""
import math  # noqa: F401

import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry  # noqa: F401

from psr_hero.utils import V_MAX, W_MAX, clamp, pose_from_odom, wrap_angle  # noqa: F401

RING_RADIUS = 0.40


class Sumo:
    def __init__(self):
        rospy.init_node("sumo")
        self.robot = rospy.get_param("~robot", 0)
        self.opponent = rospy.get_param("~opponent", 1)
        self.me = None  # (x, y, yaw)
        self.speed = 0.0  # own forward speed, m/s
        self.opp = None  # (x, y, yaw)

        # Ready: the publisher for the velocity command.
        self.pub = rospy.Publisher("/hero_%d/cmd_vel" % self.robot, Twist, queue_size=1)

        # TODO 1 (ROS): subscribe to the odometry of your robot (self.robot) -> self.on_me
        #               and of the opponent (self.opponent) -> self.on_opp.

    def on_me(self, msg):
        # TODO 1 (ROS): self.me = pose_from_odom(msg); self.speed = msg.twist.twist.linear.x
        pass

    def on_opp(self, msg):
        # TODO 1 (ROS): self.opp = pose_from_odom(msg)
        pass

    def compute_command(self, me, opp, speed, now):
        """TODO 2: choose (linear_x, angular_z).

        me, opp: (x, y, yaw). speed: own forward speed (m/s). now: time (s).
        """
        return 0.0, 0.0

    def run(self):
        rate = rospy.Rate(20)
        while not rospy.is_shutdown():
            if self.me is None or self.opp is None:
                rospy.logwarn_throttle(2.0, "waiting for odometry (TODO 1)")
            else:
                v, w = self.compute_command(self.me, self.opp, self.speed, rospy.get_time())
                cmd = Twist()
                cmd.linear.x, cmd.angular.z = v, w
                self.pub.publish(cmd)
            rate.sleep()


if __name__ == "__main__":
    Sumo().run()
