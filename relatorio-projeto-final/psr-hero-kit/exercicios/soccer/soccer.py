#!/usr/bin/env python3
"""Soccer, one team of three (student template).

Run one node per team: `_team:=blue` (robots 0, 1, 2) attacks +x and
`_team:=red` (robots 3, 4, 5) attacks -x. The field is 1.8 x 1.2 m with the
centre at (0, 0) and a 0.40 m wide goal in the middle of each short side. The
ball is an orange golf ball that you push; a goal counts when its centre crosses the goal line.

Topics:
  /hero_N/odom   nav_msgs/Odometry   pose of every robot (N = 0..5)
  /ball/odom     nav_msgs/Odometry   ball position and velocity (world frame)
  /hero_N/cmd_vel  geometry_msgs/Twist   your commands, one topic per robot
  /game/state    std_msgs/String       JSON with the score

Run:  ./run.sh run soccer      (see README.md in this folder)
"""
import math  # noqa: F401

import rospy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry  # noqa: F401

from psr_hero.utils import V_MAX, W_MAX, clamp, pose_from_odom, wrap_angle  # noqa: F401

FIELD_L, FIELD_W = 1.8, 1.2
GOAL_W = 0.40
TEAMS = {"blue": (0, +1), "red": (3, -1)}  # first robot id, attack direction on x


class Soccer:
    def __init__(self):
        rospy.init_node("soccer")
        team = rospy.get_param("~team", "blue")
        self.first, self.attack = TEAMS[team]
        self.ids = [self.first + k for k in range(3)]
        self.poses = {}  # id -> (x, y, yaw), for all 6 robots
        self.ball = None  # (x, y)

        # Ready: one publisher per robot of the team.
        self.pubs = {i: rospy.Publisher("/hero_%d/cmd_vel" % i, Twist, queue_size=1) for i in self.ids}

        # TODO 1 (ROS): subscribe to /hero_<i>/odom for i in 0..5 (-> self.on_odom, remember
        #               which i the message belongs to) and to /ball/odom (-> self.on_ball).

    def on_odom(self, msg, i):
        # TODO 1 (ROS): self.poses[i] = pose_from_odom(msg)
        pass

    def on_ball(self, msg):
        # TODO 1 (ROS): self.ball = (x, y) from msg.pose.pose.position
        pass

    def compute_commands(self, poses, ball):
        """TODO 2: return a list of three (linear_x, angular_z), one per robot of your team.

        poses: dict id -> (x, y, yaw) for all six robots. ball: (x, y).
        self.ids lists your robots; self.attack is +1 if you attack towards +x, -1 otherwise.
        Hint: start with one striker that gets behind the ball and pushes it to the goal.
        """
        return [(0.0, 0.0)] * 3

    def run(self):
        rate = rospy.Rate(20)
        while not rospy.is_shutdown():
            if self.ball is None or len(self.poses) < 6:
                rospy.logwarn_throttle(2.0, "waiting for odometry and ball (TODO 1)")
            else:
                for i, (v, w) in zip(self.ids, self.compute_commands(self.poses, self.ball)):
                    cmd = Twist()
                    cmd.linear.x, cmd.angular.z = v, w
                    self.pubs[i].publish(cmd)
            rate.sleep()


if __name__ == "__main__":
    Soccer().run()
