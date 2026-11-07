"""Small helpers shared by the example nodes and the student templates."""

import math

V_MAX = 0.20  # m/s, the simulator clips /cmd_vel to this
W_MAX = 4.0  # rad/s

# The 8-beam lidar: beam k points at LIDAR_FIRST_ANGLE + k * LIDAR_STEP,
# measured counter-clockwise from the robot heading. Beam 4 points forward.
LIDAR_BEAMS = 8
LIDAR_FIRST_ANGLE = -math.pi
LIDAR_STEP = 2.0 * math.pi / LIDAR_BEAMS
LIDAR_RANGE_MIN = 0.037
LIDAR_RANGE_MAX = 0.50  # reported when a beam hits nothing


def beam_angle(k):
    """Angle (rad) of lidar beam k in the robot frame."""
    return LIDAR_FIRST_ANGLE + k * LIDAR_STEP


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def wrap_angle(a):
    """Wrap an angle to [-pi, pi)."""
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def yaw_from_quaternion(q):
    """Yaw (rad) of a geometry_msgs/Quaternion that only rotates about z."""
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def pose_from_odom(msg):
    """(x, y, yaw) of a nav_msgs/Odometry message."""
    p = msg.pose.pose
    return p.position.x, p.position.y, yaw_from_quaternion(p.orientation)
