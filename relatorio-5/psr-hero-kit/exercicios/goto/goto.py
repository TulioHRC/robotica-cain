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
import math  # noqa: F401

import rospy
from geometry_msgs.msg import PointStamped, Twist  # noqa: F401
from nav_msgs.msg import Odometry  # noqa: F401

from psr_hero.utils import V_MAX, W_MAX, clamp, pose_from_odom, wrap_angle  # noqa: F401


class Goto:
    def __init__(self):
        rospy.init_node("goto")
        self.robot = rospy.get_param("~robot", 0)
        self.pose = None  # (x, y, yaw)
        self.goal = None  # (x, y)

        # Ready: the publisher for the velocity command.
        self.pub = rospy.Publisher("/hero_%d/cmd_vel" % self.robot, Twist, queue_size=1)

        # TODO 1 (ROS): subscribe to /hero_<robot>/odom (Odometry) -> self.on_odom
        #               and to /hero_<robot>/goal (PointStamped) -> self.on_goal.

    def on_odom(self, msg):
        # TODO 1 (ROS): store the pose. pose_from_odom(msg) returns (x, y, yaw).
        pass

    def on_goal(self, msg):
        # TODO 1 (ROS): store the goal point (msg.point.x, msg.point.y).
        pass

    def compute_command(self, pose, goal):
        """TODO 2: a controller that drives the robot to the goal.

        pose: (x, y, yaw), goal: (x, y). Returns (linear_x, angular_z).
        Hint: compute the heading error (use wrap_angle), turn proportionally to
        it and move forward only when the robot is roughly pointing at the goal.
        """
        return 0.0, 0.0

    def run(self):
        rate = rospy.Rate(20)
        while not rospy.is_shutdown():
            if self.pose is None or self.goal is None:
                rospy.logwarn_throttle(2.0, "waiting for pose and goal (TODO 1)")
            else:
                v, w = self.compute_command(self.pose, self.goal)
                cmd = Twist()
                cmd.linear.x, cmd.angular.z = v, w
                self.pub.publish(cmd)
            rate.sleep()


if __name__ == "__main__":
    Goto().run()
