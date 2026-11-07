"""Sumo: push the other robot out of a circular ring."""

from __future__ import annotations

import math

from .base import Event, Pose, Scenario, Static

RING_RADIUS = 0.40
ROUND_TIME = 40.0
PLATFORM_HEIGHT = 0.06  # m, the ring is raised so that the loser falls
FALL_PAUSE = 2.5  # s to watch the fall before the next round


class Sumo(Scenario):
    name = "sumo"
    title = "Sumô"
    robots_allowed = (2,)
    robots_default = 2
    arena = {"shape": "circle", "r": RING_RADIUS}

    def setup(self):
        self.wins = [0, 0]
        self.draws = 0
        self.round_start = 0.0

    def platform(self):
        return {"r": RING_RADIUS, "h": PLATFORM_HEIGHT}

    def statics(self):
        # drawn only in the web view: the 3D ring comes from platform(); there is no wall
        return [Static("circle", 0.0, 0.0, r=RING_RADIUS, solid=False, color=(0.12, 0.12, 0.14))]

    def spawn(self):
        # small random offsets so that two identical controllers do not deadlock
        j = lambda: self.rng.uniform(-0.06, 0.06)  # noqa: E731
        return [Pose(-0.18, j(), 0.0), Pose(0.18, j(), math.pi)]

    def colors(self):
        return [(0.2, 0.55, 0.9), (0.95, 0.6, 0.15)]

    def referee(self, robots, puck):
        out = [math.hypot(r["x"], r["y"]) > RING_RADIUS for r in robots]
        if out[0] and out[1]:
            self.draws += 1
            return Event("Empate", pause=FALL_PAUSE, poses=self.spawn())
        for i in (0, 1):
            if out[i]:
                self.wins[1 - i] += 1
                return Event(f"hero_{1 - i} venceu", pause=FALL_PAUSE, poses=self.spawn())
        if self.t - self.round_start > ROUND_TIME:
            self.draws += 1
            return Event("Empate (tempo)", poses=self.spawn())
        return None

    def public(self):
        return {"wins": list(self.wins), "draws": self.draws,
                "ring_radius": RING_RADIUS, "round_time": round(self.t - self.round_start, 1)}

    def scoreboard(self):
        return f"hero_0  {self.wins[0]}  x  {self.wins[1]}  hero_1     empates: {self.draws}"

    def reset(self):
        self.setup()
