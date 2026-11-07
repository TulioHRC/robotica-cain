#!/usr/bin/env python3
"""Bridge between the Genesis simulator (TCP, JSON lines) and ROS 1.

Publishes, for every robot N:
  /hero_N/odom   nav_msgs/Odometry      ground-truth pose in the 'world' frame
  /hero_N/laser  sensor_msgs/LaserScan  8 beams, range 0.037 .. 0.5 m
  /hero_N/goal   geometry_msgs/PointStamped   (go-to-goal scenario only)
and, when the scenario has them:
  /ball/odom     nav_msgs/Odometry      the puck (soccer)
  /game/state    std_msgs/String        JSON with the score / round information
  /flag/blue, /flag/red   geometry_msgs/PointStamped   current flag positions (ctf)
  /hero_N/has_flag        std_msgs/Bool                 robot N carries the enemy flag (ctf)

Subscribes to /hero_N/cmd_vel (and /hero_N/velocity_controller/cmd_vel, the
topic used by the real robot) and /hero_N/led.
"""
import json
import math
import socket
import threading
import time

import rospy
from geometry_msgs.msg import PointStamped, Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, ColorRGBA, String

from psr_hero.utils import LIDAR_BEAMS, LIDAR_FIRST_ANGLE, LIDAR_RANGE_MAX, LIDAR_RANGE_MIN, LIDAR_STEP


def quaternion_z(yaw):
    return 0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0)


class Bridge:
    def __init__(self):
        self.host = rospy.get_param("~host", "sim")
        self.port = int(rospy.get_param("~port", 11312))
        self.sock = None
        self.send_lock = threading.Lock()
        self.pubs = {}
        self.ball_pub = rospy.Publisher("/ball/odom", Odometry, queue_size=1)
        self.game_pub = rospy.Publisher("/game/state", String, queue_size=1)
        self.flag_pubs = {}
        self.has_flag_pubs = {}
        self.n = 0
        self.count = 0

    # --- ROS -> simulator ------------------------------------------------------

    def send(self, msg):
        with self.send_lock:
            if self.sock is None:
                return
            try:
                self.sock.sendall((json.dumps(msg) + "\n").encode())
            except OSError:
                pass

    def on_cmd(self, msg, i):
        self.send({"type": "cmd_vel", "id": i, "lin": msg.linear.x, "ang": msg.angular.z})

    def on_led(self, msg, i):
        self.send({"type": "led", "id": i, "r": msg.r, "g": msg.g, "b": msg.b})

    def setup_robots(self, layout):
        self.n = len(layout["colors"])
        for i in range(self.n):
            ns = "/hero_%d" % i
            self.pubs[i] = {
                "odom": rospy.Publisher(ns + "/odom", Odometry, queue_size=1),
                "laser": rospy.Publisher(ns + "/laser", LaserScan, queue_size=1),
                "goal": rospy.Publisher(ns + "/goal", PointStamped, queue_size=1),
            }
            rospy.Subscriber(ns + "/cmd_vel", Twist, self.on_cmd, i, queue_size=1)
            rospy.Subscriber(ns + "/velocity_controller/cmd_vel", Twist, self.on_cmd, i, queue_size=1)
            rospy.Subscriber(ns + "/led", ColorRGBA, self.on_led, i, queue_size=1)
        rospy.loginfo("scenario '%s' with %d robot(s)", layout["scenario"], self.n)

    # --- simulator -> ROS ------------------------------------------------------

    def publish_state(self, st):
        self.count += 1
        if self.count % 2:  # 50 Hz from the simulator, 25 Hz on the topics
            return
        stamp = rospy.Time.now()
        for r in st["robots"]:
            i = r["id"]
            if i not in self.pubs:
                continue
            self.pubs[i]["odom"].publish(self.odom(stamp, r["x"], r["y"], r["yaw"], r["v"], r["w"], "hero_%d/base_link" % i))

            scan = LaserScan()
            scan.header.stamp = stamp
            scan.header.frame_id = "hero_%d/laser_link" % i
            scan.angle_min = LIDAR_FIRST_ANGLE
            scan.angle_increment = LIDAR_STEP
            scan.angle_max = LIDAR_FIRST_ANGLE + (LIDAR_BEAMS - 1) * LIDAR_STEP
            scan.time_increment = 0.0
            scan.scan_time = 0.04
            scan.range_min = LIDAR_RANGE_MIN
            scan.range_max = LIDAR_RANGE_MAX
            scan.ranges = r["ranges"]
            self.pubs[i]["laser"].publish(scan)

        for i, g in enumerate(st.get("goals", [])):
            if g is not None and i in self.pubs:
                msg = PointStamped()
                msg.header.stamp = stamp
                msg.header.frame_id = "world"
                msg.point.x, msg.point.y = g
                self.pubs[i]["goal"].publish(msg)

        puck = st.get("puck")
        if puck:
            vx, vy = puck["vx"], puck["vy"]
            odom = self.odom(stamp, puck["x"], puck["y"], 0.0, 0.0, 0.0, "ball")
            odom.twist.twist.linear.x, odom.twist.twist.linear.y = vx, vy  # world frame
            self.ball_pub.publish(odom)

        for m in st.get("markers", []):
            if m.get("kind") == "flag":
                if m["team"] not in self.flag_pubs:
                    self.flag_pubs[m["team"]] = rospy.Publisher("/flag/" + m["team"], PointStamped, queue_size=1)
                msg = PointStamped()
                msg.header.stamp = stamp
                msg.header.frame_id = "world"
                msg.point.x, msg.point.y = m["x"], m["y"]
                self.flag_pubs[m["team"]].publish(msg)

        for i, carrying in enumerate(st.get("game", {}).get("carrying", [])):
            if i not in self.has_flag_pubs:
                self.has_flag_pubs[i] = rospy.Publisher("/hero_%d/has_flag" % i, Bool, queue_size=1)
            self.has_flag_pubs[i].publish(Bool(data=bool(carrying)))

        game = dict(st.get("game", {}))
        game["t"] = round(st["t"], 2)
        game["message"] = st.get("message", "")
        self.game_pub.publish(String(data=json.dumps(game)))

    @staticmethod
    def odom(stamp, x, y, yaw, v, w, child):
        msg = Odometry()
        msg.header.stamp = stamp
        msg.header.frame_id = "world"
        msg.child_frame_id = child
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        q = quaternion_z(yaw)
        msg.pose.pose.orientation.x, msg.pose.pose.orientation.y = q[0], q[1]
        msg.pose.pose.orientation.z, msg.pose.pose.orientation.w = q[2], q[3]
        msg.twist.twist.linear.x = v
        msg.twist.twist.angular.z = w
        return msg

    # --- connection loop -------------------------------------------------------

    def run(self):
        while not rospy.is_shutdown():
            try:
                sock = socket.create_connection((self.host, self.port), timeout=3.0)
            except OSError as err:
                rospy.logwarn_throttle(5.0, "waiting for the simulator at %s:%d (%s)", self.host, self.port, err)
                time.sleep(1.0)
                continue
            sock.settimeout(1.0)
            rospy.loginfo("connected to the simulator at %s:%d", self.host, self.port)
            with self.send_lock:
                self.sock = sock
            self.read_loop(sock)
            with self.send_lock:
                self.sock = None
            rospy.logwarn("simulator connection lost")

    def read_loop(self, sock):
        buf = b""
        while not rospy.is_shutdown():
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                msg = json.loads(line)
                if msg["type"] == "layout" and not self.pubs:
                    self.setup_robots(msg["layout"])
                elif msg["type"] == "state" and self.pubs:
                    self.publish_state(msg)


if __name__ == "__main__":
    rospy.init_node("hero_bridge")
    Bridge().run()
