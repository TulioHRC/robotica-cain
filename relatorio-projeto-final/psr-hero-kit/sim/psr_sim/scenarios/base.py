"""Scenario interface: arena, spawn poses and referee rules."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from ..geometry import box_segments

WALL = 0.02  # wall thickness (m)

Color = tuple[float, float, float]


@dataclass
class Pose:
    x: float
    y: float
    yaw: float = 0.0


@dataclass
class Static:
    """Fixed shape. kind is 'box' (w x h), 'circle' (radius r) or 'ring' (outer
    radius r, line width w). Non-solid shapes are paint on the floor: `layer`
    stacks them (higher on top); with `height` they are tall but still not solid."""

    kind: str
    x: float
    y: float
    w: float = 0.0
    h: float = 0.0
    r: float = 0.0
    solid: bool = True  # False: drawn only (floors, markings)
    color: Color = (0.45, 0.45, 0.5)
    layer: int = 0
    height: float | None = None

    def segments(self) -> list[tuple[float, float, float, float]]:
        return box_segments(self.x, self.y, self.w, self.h) if self.kind == "box" else []


@dataclass
class PuckSpec:
    radius: float = 0.04
    mass: float = 0.03
    friction: float = 0.05  # sliding friction coefficient (decelerates the puck)
    color: Color = (1.0, 0.85, 0.1)


@dataclass
class Event:
    """What the referee decides after a step: freeze for a while, then reset."""

    message: str
    pause: float = 2.0
    poses: list[Pose | None] | None = None  # None keeps that robot where it is
    puck: Pose | None = None


def rect_walls(width: float, height: float, color: Color = (0.45, 0.45, 0.5)) -> list[Static]:
    """Four walls whose inner faces enclose [-width/2, width/2] x [-height/2, height/2]."""
    t = WALL
    return [
        Static("box", 0.0, height / 2 + t / 2, width + 2 * t, t, color=color),
        Static("box", 0.0, -height / 2 - t / 2, width + 2 * t, t, color=color),
        Static("box", width / 2 + t / 2, 0.0, t, height, color=color),
        Static("box", -width / 2 - t / 2, 0.0, t, height, color=color),
    ]


def paint_line(x0: float, y0: float, x1: float, y1: float, t: float, color: Color, layer: int = 2) -> Static:
    """A painted floor line along x or y (axis-aligned), t metres wide."""
    horizontal = y0 == y1
    w = abs(x1 - x0) + t if horizontal else t
    h = t if horizontal else abs(y1 - y0) + t
    return Static("box", (x0 + x1) / 2, (y0 + y1) / 2, w, h, solid=False, color=color, layer=layer)


def paint_outline(cx: float, cy: float, w: float, h: float, t: float, color: Color, layer: int = 2) -> list[Static]:
    """Rectangle outline whose outer edge is w x h, drawn t thick."""
    return [
        Static("box", cx, cy + h / 2 - t / 2, w, t, solid=False, color=color, layer=layer),
        Static("box", cx, cy - h / 2 + t / 2, w, t, solid=False, color=color, layer=layer),
        Static("box", cx + w / 2 - t / 2, cy, t, h - 2 * t, solid=False, color=color, layer=layer),
        Static("box", cx - w / 2 + t / 2, cy, t, h - 2 * t, solid=False, color=color, layer=layer),
    ]


class Scenario:
    name = "base"
    title = "Base"
    robots_allowed: tuple[int, ...] = (1,)
    robots_default = 1
    arena: dict = {"shape": "rect", "w": 2.0, "h": 2.0}

    def __init__(self, n_robots: int | None = None, seed: int | None = None):
        n = n_robots if n_robots is not None else self.robots_default
        if n not in self.robots_allowed:
            raise ValueError(
                f"scenario '{self.name}' supports {self.robots_allowed} robots, got {n}"
            )
        self.n = n
        self.rng = random.Random(seed)
        self.t = 0.0
        self.round_start = 0.0
        self.paused_until = -1.0
        self.pending: Event | None = None
        self.message = ""
        self.setup()

    # --- layout (overridden) -------------------------------------------------

    def setup(self) -> None:
        pass

    def statics(self) -> list[Static]:
        return []

    def spawn(self) -> list[Pose]:
        raise NotImplementedError

    def puck_spec(self) -> PuckSpec | None:
        return None

    def puck_spawn(self) -> Pose | None:
        return None

    def colors(self) -> list[Color]:
        return [(0.2, 0.7, 0.3)] * self.n

    def teams(self) -> list[str | None]:
        return [None] * self.n

    def flags(self) -> list[dict]:
        """Capture-the-flag flags drawn in 3D: [{'x', 'y', 'color'}], updated every tick."""
        return []

    def platform(self) -> dict | None:
        """Raised circular platform {'r', 'h'} that robots can fall off, if any."""
        return None

    def set_goal(self, i: int, x: float, y: float) -> None:
        """Move robot i's goal (web view click); only scenarios with goals use it."""

    def markers(self) -> list[dict]:
        """Dynamic shapes drawn by the web view (goals, targets)."""
        return []

    def goals(self) -> list[tuple[float, float] | None]:
        """Per-robot goal point published on /hero_N/goal, if the scenario has one."""
        return [None] * self.n

    def referee(self, robots: list[dict], puck: dict | None) -> Event | None:
        """Called every control tick while the game is running."""
        return None

    def public(self) -> dict:
        """Game state published on /game/state."""
        return {}

    def held(self, i: int) -> bool:
        """True while robot i is held in place by the rules (commands are ignored)."""
        return False

    def notice(self) -> str:
        """Short message shown while the game keeps running (no pause)."""
        return ""

    def scoreboard(self) -> str:
        """One line of text for the scoreboard drawn in the Genesis window."""
        return ""

    def reset(self) -> None:
        """Restart the scoreboard (web 'reset' button)."""

    # --- driven by the world --------------------------------------------------

    @property
    def frozen(self) -> bool:
        return self.t < self.paused_until

    def layout(self) -> dict:
        statics = self.statics()
        return {
            "scenario": self.name,
            "title": self.title,
            "arena": self.arena,
            "statics": [
                {
                    "kind": s.kind, "x": s.x, "y": s.y, "w": s.w, "h": s.h, "r": s.r,
                    "solid": s.solid, "color": list(s.color), "height": s.height,
                }
                for s in statics
            ],
            "colors": [list(c) for c in self.colors()],
            "teams": self.teams(),
            "puck": None if self.puck_spec() is None else {"r": self.puck_spec().radius,
                                                            "color": list(self.puck_spec().color)},
        }

    def dist(self, a: dict, b: dict) -> float:
        return math.hypot(a["x"] - b["x"], a["y"] - b["y"])
