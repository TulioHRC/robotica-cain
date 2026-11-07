"""Obstacle avoidance: square arena with a cylinder in the middle."""

from __future__ import annotations

import math

from .base import Pose, Scenario, Static, rect_walls


class Avoid(Scenario):
    name = "avoid"
    title = "Desvio de obstáculo"
    robots_allowed = (1, 2)
    arena = {"shape": "rect", "w": 2.0, "h": 2.0}

    def statics(self):
        return rect_walls(2.0, 2.0) + [
            Static("circle", 0.0, 0.0, r=0.15, color=(0.85, 0.35, 0.2)),
        ]

    def spawn(self):
        return [Pose(-0.7, 0.0, 0.0), Pose(0.7, 0.4, math.pi)][: self.n]

    def colors(self):
        return [(0.2, 0.55, 0.9), (0.95, 0.6, 0.15)][: self.n]

    def scoreboard(self):
        return f"Tempo: {int(self.t)} s"
