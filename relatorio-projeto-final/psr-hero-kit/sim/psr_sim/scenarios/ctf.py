"""Capture the flag, 1 or 2 robots per team: steal the enemy flag and bring it home."""

from __future__ import annotations

import math

from .base import Event, Pose, Scenario, Static, paint_line, paint_outline, rect_walls

SIZE = 1.6
BASE_X = 0.62  # flag and base centre of each team, at (-BASE_X, 0) blue and (+BASE_X, 0) red
BASE_RADIUS = 0.14  # a robot carrying the enemy flag scores inside this circle
PICKUP_DISTANCE = 0.07  # touching the enemy flag picks it up
TAG_DISTANCE = 0.10  # a defender tags an intruder this close, in the defender's own half
ROUND_TIME = 90.0  # without a point or a tag for this long: draw, back to the start
HOLD_TIME = 4.0  # s a tagged robot is held in place; the game goes on for everybody else
IMMUNE_TIME = 1.5  # s after the release in which it cannot be held again
NOTICE_TIME = 2.5  # s the "held" message stays on screen
SCORE_PAUSE = 2.0

BLUE = (0.15, 0.4, 1.0)
RED = (1.0, 0.18, 0.12)
TEAMS = ("blue", "red")
FLOOR = (0.88, 0.89, 0.93)
GRID = (0.80, 0.82, 0.88)
BAND = (0.96, 0.76, 0.18)  # safety band along the walls
BOARD = (0.20, 0.21, 0.26)


def _tint(color, k):
    """Blend a colour towards white: k=0 white, k=1 the colour."""
    return tuple(1.0 - k * (1.0 - c) for c in color)


class CaptureTheFlag(Scenario):
    name = "ctf"
    title = "Rouba-bandeira"
    robots_allowed = (2, 4)
    robots_default = 4
    arena = {"shape": "rect", "w": SIZE, "h": SIZE}

    def setup(self):
        self.score = [0, 0]
        self.tags = [0] * self.n  # times each robot was held
        self.hold_until = [0.0] * self.n
        self.immune_until = [0.0] * self.n
        self.notice_text = ""
        self.notice_until = 0.0
        self.round_start = 0.0
        self.carrier: list[int | None] = [None, None]  # carrier[team]: robot holding that team's flag
        self.flag_xy = [self.home(0), self.home(1)]

    def held(self, i):
        return self.t < self.hold_until[i]

    def notice(self):
        return self.notice_text if self.t < self.notice_until else ""

    def team_of(self, i: int) -> int:
        """hero_0.. are blue, the second half red (2 robots: 0 blue, 1 red; 4: 0,1 blue and 2,3 red)."""
        return i * 2 // self.n

    @staticmethod
    def home(team: int) -> tuple[float, float]:
        return (-BASE_X if team == 0 else BASE_X, 0.0)

    @staticmethod
    def own_half(team: int, x: float) -> bool:
        return x < 0.0 if team == 0 else x > 0.0

    def statics(self):
        paint = [Static("box", 0.0, 0.0, SIZE, SIZE, solid=False, color=FLOOR)]
        # each team's half is tinted, with the base circle a little stronger
        paint.append(Static("box", -SIZE / 4, 0.0, SIZE / 2, SIZE, solid=False, color=_tint(BLUE, 0.10), layer=1))
        paint.append(Static("box", SIZE / 4, 0.0, SIZE / 2, SIZE, solid=False, color=_tint(RED, 0.10), layer=1))
        paint += paint_outline(0.0, 0.0, SIZE, SIZE, 0.05, BAND, layer=1)
        for k in range(-3, 4):  # a 0.2 m grid, for judging distances
            c = 0.2 * k
            paint.append(paint_line(c, -0.75, c, 0.75, 0.004, GRID, layer=2))
            paint.append(paint_line(-0.75, c, 0.75, c, 0.004, GRID, layer=2))
        paint.append(paint_line(0.0, -SIZE / 2 + 0.05, 0.0, SIZE / 2 - 0.05, 0.012, (0.45, 0.47, 0.56), layer=3))
        for team, color in ((0, BLUE), (1, RED)):
            hx, hy = self.home(team)
            paint.append(Static("circle", hx, hy, r=BASE_RADIUS, solid=False, color=_tint(color, 0.28), layer=3))
            paint.append(Static("ring", hx, hy, r=BASE_RADIUS, w=0.010, solid=False, color=color, layer=4))
            paint.append(Static("circle", hx, hy, r=0.014, solid=False, color=color, layer=4))
        return paint + rect_walls(SIZE, SIZE, BOARD)

    def spawn(self):
        return [self.respawn(i) for i in range(self.n)]

    def respawn(self, i: int) -> Pose:
        """Start line in front of the own flag; with two robots per team, one in each lane."""
        team = self.team_of(i)
        hx, _ = self.home(team)
        per_team = self.n // 2
        if per_team == 1:
            y = self.rng.uniform(-0.45, 0.45)
        else:
            lane = 0.28 if i % per_team == 0 else -0.28
            y = (lane if team == 0 else -lane) + self.rng.uniform(-0.06, 0.06)  # red mirrors blue by rotation
        return Pose(hx + (0.15 if team == 0 else -0.15), y, 0.0 if team == 0 else math.pi)

    def colors(self):
        return [BLUE if self.team_of(i) == 0 else RED for i in range(self.n)]

    def teams(self):
        return [TEAMS[self.team_of(i)] for i in range(self.n)]

    def flags(self):
        return [{"x": self.flag_xy[t][0], "y": self.flag_xy[t][1], "color": c, "team": TEAMS[t]}
                for t, c in ((0, BLUE), (1, RED))]

    def markers(self):
        return [{"kind": "flag", "x": f["x"], "y": f["y"], "color": list(f["color"]), "team": f["team"]}
                for f in self.flags()]

    def _drop_flags(self):
        """New round: flags home, nobody held."""
        self.carrier = [None, None]
        self.flag_xy = [self.home(0), self.home(1)]
        self.hold_until = [0.0] * self.n
        self.immune_until = [0.0] * self.n

    def referee(self, robots, puck):
        # a carried flag follows its carrier (a little behind the centre)
        for team in (0, 1):
            c = self.carrier[team]
            if c is not None:
                r = robots[c]
                self.flag_xy[team] = (r["x"] - 0.012 * math.cos(r["yaw"]), r["y"] - 0.012 * math.sin(r["yaw"]))

        # 1) hold: a free robot in its own half stops an intruder for HOLD_TIME s; the intruder drops
        #    the flag (back to its base) and everybody else keeps playing
        for i in range(self.n):
            if self.held(i):
                continue
            for j in range(self.n):
                ti, tj = self.team_of(i), self.team_of(j)
                if ti == tj or self.held(j) or self.t < self.immune_until[j]:
                    continue
                if (self.own_half(ti, robots[i]["x"]) and self.own_half(ti, robots[j]["x"])
                        and self.dist(robots[i], robots[j]) < TAG_DISTANCE):
                    self.tags[j] += 1
                    self.hold_until[j] = self.t + HOLD_TIME
                    self.immune_until[j] = self.t + HOLD_TIME + IMMUNE_TIME
                    if self.carrier[ti] == j:  # j was carrying i's team flag
                        self.carrier[ti] = None
                        self.flag_xy[ti] = self.home(ti)
                    self.notice_text = f"hero_{i} segurou o hero_{j} por {HOLD_TIME:.0f} s"
                    self.notice_until = self.t + NOTICE_TIME

        # 2) pick up the enemy flag
        for i in range(self.n):
            enemy = 1 - self.team_of(i)
            if self.carrier[enemy] is None and math.hypot(
                robots[i]["x"] - self.flag_xy[enemy][0], robots[i]["y"] - self.flag_xy[enemy][1]
            ) < PICKUP_DISTANCE:
                self.carrier[enemy] = i

        # 3) score: carrying the enemy flag into the own base
        for i in range(self.n):
            team = self.team_of(i)
            if self.carrier[1 - team] == i:
                hx, hy = self.home(team)
                if math.hypot(robots[i]["x"] - hx, robots[i]["y"] - hy) < BASE_RADIUS:
                    self.score[team] += 1
                    self._drop_flags()
                    return Event(f"Ponto do {'azul' if team == 0 else 'vermelho'}!", pause=SCORE_PAUSE,
                                 poses=self.spawn())

        if self.t - self.round_start > ROUND_TIME:
            self._drop_flags()
            return Event("Empate (tempo)", pause=SCORE_PAUSE, poses=self.spawn())
        return None

    def public(self):
        return {
            "score": list(self.score),
            "tags": list(self.tags),
            "held": [self.held(i) for i in range(self.n)],
            # robot i holds the enemy flag
            "carrying": [self.carrier[1 - self.team_of(i)] == i for i in range(self.n)],
            "base_x": BASE_X, "base_radius": BASE_RADIUS,
            "round_time": round(self.t - self.round_start, 1),
        }

    def scoreboard(self):
        return f"AZUL  {self.score[0]}  x  {self.score[1]}  VERMELHO"

    def reset(self):
        self.setup()
