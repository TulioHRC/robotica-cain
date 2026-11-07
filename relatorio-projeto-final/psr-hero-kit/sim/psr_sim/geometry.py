"""Planar geometry and the HeRo lidar model (8 beams, 0.5 m range)."""

from __future__ import annotations

import math

import numpy as np

N_BEAMS = 8
RANGE_MIN = 0.037  # HeRo body radius: the beam starts at the robot centre
RANGE_MAX = 0.50  # value reported when a beam hits nothing
ANGLE_MIN = -math.pi
ANGLE_INCREMENT = 2.0 * math.pi / N_BEAMS
BEAM_ANGLES = ANGLE_MIN + ANGLE_INCREMENT * np.arange(N_BEAMS)

ROBOT_RADIUS = 0.037


def wrap_angle(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def box_segments(x: float, y: float, w: float, h: float) -> list[tuple[float, float, float, float]]:
    """Edges of an axis-aligned box centred at (x, y)."""
    x0, x1, y0, y1 = x - w / 2, x + w / 2, y - h / 2, y + h / 2
    return [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]


def cast_beams(
    origin: np.ndarray,
    yaw: float,
    circles: np.ndarray,
    segments: np.ndarray,
) -> np.ndarray:
    """Range of every beam from `origin`, clipped to [RANGE_MIN, RANGE_MAX].

    circles: (n, 3) array of x, y, r. segments: (m, 4) array of x0, y0, x1, y1.
    Beam k points at yaw + BEAM_ANGLES[k] (counter-clockwise positive).
    """
    angles = BEAM_ANGLES + yaw
    d = np.stack([np.cos(angles), np.sin(angles)], axis=1)  # (B, 2)
    best = np.full(N_BEAMS, np.inf)

    if len(circles):
        f = origin[None, :] - circles[:, :2]  # (C, 2)
        b = d @ f.T  # (B, C)
        c = (f * f).sum(axis=1) - circles[:, 2] ** 2  # (C,)
        disc = b * b - c[None, :]
        with np.errstate(invalid="ignore"):
            t = -b - np.sqrt(disc)
        ok = (disc >= 0.0) & (t >= 0.0)
        best = np.minimum(best, np.where(ok, t, np.inf).min(axis=1))

    if len(segments):
        p = segments[:, :2]
        e = segments[:, 2:] - p  # (S, 2)
        w = p - origin[None, :]  # (S, 2)
        den = d[:, None, 0] * e[None, :, 1] - d[:, None, 1] * e[None, :, 0]  # (B, S)
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (w[None, :, 0] * e[None, :, 1] - w[None, :, 1] * e[None, :, 0]) / den
            u = (w[None, :, 0] * d[:, None, 1] - w[None, :, 1] * d[:, None, 0]) / den
        ok = (np.abs(den) > 1e-12) & (t >= 0.0) & (u >= 0.0) & (u <= 1.0)
        best = np.minimum(best, np.where(ok, t, np.inf).min(axis=1))

    return np.clip(best, RANGE_MIN, RANGE_MAX)
