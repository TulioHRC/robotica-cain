"""Go-to-goal: an empty arena where each robot gets a goal point."""

from __future__ import annotations

import math

from .base import Pose, Scenario, rect_walls

REACH_RADIUS = 0.06
MARGIN = 0.25


class Goto(Scenario):
    name = "goto"
    title = "Navegação goal to goal"
    robots_allowed = (1, 2)
    arena = {"shape": "rect", "w": 2.0, "h": 2.0}

    def setup(self):
        self.reached = [0] * self.n
        self.goal_t = [0.0] * self.n
        self.last_time = [0.0] * self.n
        self.goal_xy = [self._new_goal(None) for _ in range(self.n)]

    def _new_goal(self, near):
        for _ in range(100):
            g = (self.rng.uniform(-1 + MARGIN, 1 - MARGIN), self.rng.uniform(-1 + MARGIN, 1 - MARGIN))
            if near is None or math.hypot(g[0] - near[0], g[1] - near[1]) > 0.6:
                return g
        return g

    def statics(self):
        return rect_walls(2.0, 2.0)

    def spawn(self):
        return [Pose(-0.6, -0.6, 0.0), Pose(0.6, 0.6, math.pi)][: self.n]

    def colors(self):
        return [(0.2, 0.55, 0.9), (0.95, 0.6, 0.15)][: self.n]

    def goals(self):
        return list(self.goal_xy)

    def markers(self):
        return [
            {"kind": "target", "id": i, "x": g[0], "y": g[1], "r": REACH_RADIUS, "color": list(c)}
            for i, (g, c) in enumerate(zip(self.goal_xy, self.colors()))
        ]

    def set_goal(self, i, x, y):
        if 0 <= i < self.n:
            lim = 1.0 - 0.05
            self.goal_xy[i] = (max(-lim, min(lim, x)), max(-lim, min(lim, y)))

    def referee(self, robots, puck):
        for i, robot in enumerate(robots):
            gx, gy = self.goal_xy[i]
            if math.hypot(robot["x"] - gx, robot["y"] - gy) < REACH_RADIUS:
                self.reached[i] += 1
                self.last_time[i] = self.t - self.goal_t[i]
                self.goal_t[i] = self.t
                self.goal_xy[i] = self._new_goal((robot["x"], robot["y"]))
        return None

    def public(self):
        return {"reached": list(self.reached), "last_goal_time": [round(x, 2) for x in self.last_time]}

    def scoreboard(self):
        return "Metas atingidas:  " + "   ".join(f"hero_{i}: {n}" for i, n in enumerate(self.reached))

    def reset(self):
        self.setup()
