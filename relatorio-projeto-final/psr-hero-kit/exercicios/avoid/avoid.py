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
import rospy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan  # noqa: F401  (you will need it for TODO 1)

from psr_hero.utils import V_MAX, W_MAX, beam_angle, clamp  # noqa: F401


class Avoid:
    def __init__(self):
        rospy.init_node("avoid")
        self.robot = rospy.get_param("~robot", 0)
        self.scan = None

        # Ready: the publisher for the velocity command.
        self.pub = rospy.Publisher("/hero_%d/cmd_vel" % self.robot, Twist, queue_size=1)

        # TODO 1 (ROS): subscribe to the lidar topic of this robot
        #   (/hero_<robot>/laser, message type LaserScan) and call self.on_scan.

    def on_scan(self, scan):
        # TODO 1 (ROS): keep the latest message in self.scan.
        pass

    def compute_command(self, ranges):
        """TODO 2: turn the 8 lidar ranges into a velocity command.

        ranges: list with 8 floats (m). Returns (linear_x [m/s], angular_z [rad/s]).
        Linear speed is limited to V_MAX = 0.2 m/s and angular speed to W_MAX = 4 rad/s.
        Hint: the robot should keep moving, slow down when something is in front
        and turn away from the side where the obstacle is closer.
        """
        return 0.0, 0.0

    def publish(self, v, w):
        cmd = Twist()
        cmd.linear.x = v
        cmd.angular.z = w
        self.pub.publish(cmd)

    def run(self):
        rate = rospy.Rate(20)
        while not rospy.is_shutdown():
            if self.scan is None:
                rospy.logwarn_throttle(2.0, "no lidar data yet: is the subscriber of TODO 1 in place?")
            else:
                self.publish(*self.compute_command(list(self.scan.ranges)))
            rate.sleep()


if __name__ == "__main__":
    Avoid().run()
