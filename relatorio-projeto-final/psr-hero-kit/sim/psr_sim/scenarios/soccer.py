"""Soccer: 3 robots per team, a golf ball and a goal on each side."""

from __future__ import annotations

import math

from .base import WALL, Event, Pose, PuckSpec, Scenario, Static, paint_line, paint_outline

FIELD_L = 1.8  # x
FIELD_W = 1.2  # y
GOAL_W = 0.40
GOAL_DEPTH = 0.10
WALL_POST = 0.07  # visual goal posts, taller than the boards
BLUE = (0.15, 0.4, 1.0)
RED = (1.0, 0.18, 0.12)
GRASS = ((0.11, 0.40, 0.17), (0.14, 0.46, 0.20))  # mowing stripes
LINE = (0.96, 0.96, 0.96)
BOARD = (0.16, 0.17, 0.20)  # touchline boards
LINE_W = 0.010
PENALTY_DEPTH, PENALTY_WIDTH = 0.30, 0.70
GOAL_AREA_DEPTH, GOAL_AREA_WIDTH = 0.12, 0.50
CENTER_RADIUS = 0.15
STRIPES = 10


class Soccer(Scenario):
    name = "soccer"
    title = "Futebol de robôs"
    robots_allowed = (6,)
    robots_default = 6
    arena = {"shape": "rect", "w": FIELD_L + 2 * GOAL_DEPTH, "h": FIELD_W}

    def setup(self):
        self.score = [0, 0]  # [blue, red]
        self.kickoff_left = 0

    def statics(self):
        t = WALL
        L, W, G, D = FIELD_L, FIELD_W, GOAL_W, GOAL_DEPTH
        # --- floor: striped grass, goal mouths tinted with the team colour
        paint = []
        sw = L / STRIPES
        for k in range(STRIPES):
            paint.append(Static("box", -L / 2 + sw * (k + 0.5), 0.0, sw, W, solid=False, color=GRASS[k % 2]))
        for sx, team in ((-1, BLUE), (1, RED)):
            dark = tuple(0.35 * c + 0.05 for c in team)
            paint.append(Static("box", sx * (L / 2 + D / 2), 0.0, D, G, solid=False, color=dark, layer=1))
        # --- markings
        paint += paint_outline(0.0, 0.0, L, W, LINE_W, LINE)
        paint.append(paint_line(0.0, -W / 2, 0.0, W / 2, LINE_W, LINE))
        paint.append(Static("ring", 0.0, 0.0, r=CENTER_RADIUS, w=LINE_W, solid=False, color=LINE, layer=2))
        paint.append(Static("circle", 0.0, 0.0, r=0.012, solid=False, color=LINE, layer=2))
        for sx in (-1, 1):
            edge = sx * L / 2
            for depth, width in ((PENALTY_DEPTH, PENALTY_WIDTH), (GOAL_AREA_DEPTH, GOAL_AREA_WIDTH)):
                x_in = edge - sx * depth
                paint.append(paint_line(x_in, -width / 2, x_in, width / 2, LINE_W, LINE))
                for sy in (-1, 1):
                    paint.append(paint_line(x_in, sy * width / 2, edge, sy * width / 2, LINE_W, LINE))
            paint.append(Static("circle", edge - sx * 0.20, 0.0, r=0.008, solid=False, color=LINE, layer=2))
        # --- walls: dark touchline boards, team-coloured goal pockets, white posts
        walls = [
            Static("box", 0.0, W / 2 + t / 2, L + 2 * t, t, color=BOARD),
            Static("box", 0.0, -W / 2 - t / 2, L + 2 * t, t, color=BOARD),
        ]
        side = (W - G) / 2  # wall length on each side of the goal opening
        for sx, team in ((-1, BLUE), (1, RED)):
            xw = sx * (L / 2 + t / 2)
            for sy in (-1, 1):
                walls.append(Static("box", xw, sy * (G / 2 + side / 2), t, side, color=BOARD))
            # goal pocket: back wall and two side walls
            walls.append(Static("box", sx * (L / 2 + D + t / 2), 0.0, t, G + 2 * t, color=team))
            for sy in (-1, 1):
                walls.append(Static("box", sx * (L / 2 + D / 2), sy * (G / 2 + t / 2), D, t, color=team))
                walls.append(Static("circle", xw, sy * G / 2, r=0.011, solid=False, height=WALL_POST,
                                    color=(0.97, 0.97, 0.97)))
        return paint + walls

    def spawn(self):
        # small random offsets on every kickoff, so mirrored controllers do not deadlock
        j = lambda: self.rng.uniform(-0.05, 0.05)  # noqa: E731
        blue = [Pose(-0.78, 0.0, 0.0), Pose(-0.35 + j(), 0.25 + j(), 0.0), Pose(-0.35 + j(), -0.25 + j(), 0.0)]
        red = [Pose(0.78, 0.0, math.pi), Pose(0.35 + j(), -0.25 + j(), math.pi), Pose(0.35 + j(), 0.25 + j(), math.pi)]
        return blue + red

    def puck_spec(self):
        return PuckSpec(radius=0.0214, mass=0.046, friction=0.01, color=(1.0, 0.5, 0.0))

    def puck_spawn(self):
        return Pose(0.0, self.rng.uniform(-0.05, 0.05))

    def colors(self):
        return [BLUE] * 3 + [RED] * 3

    def teams(self):
        return ["blue"] * 3 + ["red"] * 3

    def markers(self):
        return [
            {"kind": "rect", "x": -FIELD_L / 2 - GOAL_DEPTH / 2, "y": 0.0, "w": GOAL_DEPTH, "h": GOAL_W,
             "color": list(BLUE)},
            {"kind": "rect", "x": FIELD_L / 2 + GOAL_DEPTH / 2, "y": 0.0, "w": GOAL_DEPTH, "h": GOAL_W,
             "color": list(RED)},
        ]

    def referee(self, robots, puck):
        if puck is None:
            return None
        inside = abs(puck["y"]) < GOAL_W / 2
        if puck["x"] > FIELD_L / 2 and inside:
            self.score[0] += 1
            return Event("Gol do azul!", poses=self.spawn(), puck=self.puck_spawn())
        if puck["x"] < -FIELD_L / 2 and inside:
            self.score[1] += 1
            return Event("Gol do vermelho!", poses=self.spawn(), puck=self.puck_spawn())
        return None

    def public(self):
        return {"blue": self.score[0], "red": self.score[1], "time": round(self.t, 1),
                "field": {"length": FIELD_L, "width": FIELD_W, "goal_width": GOAL_W}}

    def scoreboard(self):
        return f"AZUL  {self.score[0]}  x  {self.score[1]}  VERMELHO"

    def reset(self):
        self.setup()
