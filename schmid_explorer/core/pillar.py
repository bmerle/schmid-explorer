# SPDX-License-Identifier: GPL-3.0-or-later
"""Geometry of the pillar sketch: prism, slip-plane section and slip step.

The cylindrical pillar is approximated by a regular N-gon prism centred at the origin
with its axis along z of the pillar frame (see `stereo`): +z points from the substrate
to the top face, whatever the loading sense. The slip plane passes through the pillar
centre. Because the prism and a half-space are both convex, the two crystal blocks on
either side of the slip plane are obtained by clipping every prism face against the
plane (Sutherland-Hodgman). This works for any inclination of the plane, including
planes leaving the pillar through its top or bottom face.

Slip step: the block carrying the top face is translated rigidly by  amount * b,  with
b the slip direction of this block as defined in `schmid`: it follows the force,
upwards in tension (the pillar becomes longer) and downwards in compression (the
pillar becomes shorter). Since the plane normal n points into the hemisphere of the
force, this block is the one on the +n side in tension and on the -n side in
compression (`blocks`).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_EPS = 1e-12


@dataclass(frozen=True)
class PillarShape:
    radius: float = 1.0
    height: float = 3.0
    sides: int = 48


def prism_faces(shape: PillarShape = PillarShape()) -> dict:
    """Faces of the prism as vertex arrays: {'side': [...], 'top': [...], 'bottom': [...]}."""
    ring = _ring(shape)
    top = ring + [0.0, 0.0, shape.height / 2.0]
    bottom = ring - [0.0, 0.0, shape.height / 2.0]
    count = shape.sides
    sides = [
        np.array([bottom[i], bottom[(i + 1) % count], top[(i + 1) % count], top[i]])
        for i in range(count)
    ]
    return {"side": sides, "top": [top], "bottom": [bottom[::-1]]}


def clip_polygon(polygon: np.ndarray, normal, offset: float = 0.0) -> np.ndarray:
    """Part of a convex polygon inside the half-space  normal . p <= offset."""
    normal = np.asarray(normal, dtype=float)
    distance = polygon @ normal - offset
    result = []
    count = len(polygon)
    for i in range(count):
        j = (i + 1) % count
        inside_i, inside_j = distance[i] <= _EPS, distance[j] <= _EPS
        if inside_i:
            result.append(polygon[i])
        if inside_i != inside_j:
            t = distance[i] / (distance[i] - distance[j])
            result.append(polygon[i] + t * (polygon[j] - polygon[i]))
    return np.array(result) if len(result) >= 3 else np.empty((0, 3))


def section(normal, shape: PillarShape = PillarShape()) -> np.ndarray:
    """Polygon cut out of the plane through the origin (unit normal) by the prism."""
    n = np.asarray(normal, dtype=float)
    n = n / np.linalg.norm(n)
    helper = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(n, helper)
    u = u / np.linalg.norm(u)
    v = np.cross(n, u)
    size = 4.0 * (shape.radius + shape.height)
    polygon = np.array([size * (-u - v), size * (u - v), size * (u + v), size * (-u + v)])
    for face_normal, face_offset in _half_spaces(shape):
        polygon = clip_polygon(polygon, face_normal, face_offset)
        if len(polygon) == 0:
            break
    return polygon


def split(normal, shape: PillarShape = PillarShape()) -> tuple:
    """Blocks below (n.p <= 0) and above (n.p >= 0) the slip plane.

    Each block is a dict {'side': [...], 'top': [...], 'bottom': [...], 'cut': [...]}
    of face polygons; 'cut' is the slip-plane section.
    """
    n = np.asarray(normal, dtype=float)
    n = n / np.linalg.norm(n)
    faces = prism_faces(shape)
    cut = section(n, shape)
    below = {kind: [] for kind in ("side", "top", "bottom")}
    above = {kind: [] for kind in ("side", "top", "bottom")}
    for kind, polygons in faces.items():
        for polygon in polygons:
            lower = clip_polygon(polygon, n)
            upper = clip_polygon(polygon, -n)
            if len(lower):
                below[kind].append(lower)
            if len(upper):
                above[kind].append(upper)
    below["cut"] = [cut] if len(cut) else []
    above["cut"] = [cut[::-1]] if len(cut) else []
    return below, above


def blocks(normal, shape: PillarShape = PillarShape()) -> tuple:
    """The two blocks as (block resting on the substrate, block carrying the top face).

    The block carrying the top face lies on the +n side of the slip plane if the normal
    points upwards (n_z >= 0, pillar frame) and on the -n side if it points downwards.
    """
    below, above = split(normal, shape)
    return (below, above) if np.asarray(normal, dtype=float)[2] >= -_EPS else (above, below)


def translate(block: dict, displacement) -> dict:
    """Rigidly shifted copy of a block."""
    shift = np.asarray(displacement, dtype=float)
    return {kind: [polygon + shift for polygon in polygons] for kind, polygons in block.items()}


def slip_displacement(b, amount: float) -> np.ndarray:
    """Displacement of the block carrying the top face: amount * b (b = its slip direction)."""
    return amount * np.asarray(b, dtype=float)


def volume(block: dict) -> float:
    """Volume of a convex block from its faces (sum of pyramids about the centroid)."""
    polygons = [polygon for group in block.values() for polygon in group]
    if not polygons:
        return 0.0
    centre = np.mean(np.vstack(polygons), axis=0)
    total = 0.0
    for polygon in polygons:
        for i in range(1, len(polygon) - 1):
            a, b, c = polygon[0] - centre, polygon[i] - centre, polygon[i + 1] - centre
            total += abs(np.dot(a, np.cross(b, c))) / 6.0
    return total


def prism_volume(shape: PillarShape = PillarShape()) -> float:
    area = 0.5 * shape.sides * shape.radius ** 2 * np.sin(2.0 * np.pi / shape.sides)
    return area * shape.height


# --------------------------------------------------------------------------- helpers
def _ring(shape: PillarShape) -> np.ndarray:
    angles = 2.0 * np.pi * np.arange(shape.sides) / shape.sides
    return np.column_stack(
        [shape.radius * np.cos(angles), shape.radius * np.sin(angles), np.zeros(shape.sides)])


def _half_spaces(shape: PillarShape) -> list:
    """(outward normal, offset) of every prism face: the prism is  normal . p <= offset."""
    mid = 2.0 * np.pi * (np.arange(shape.sides) + 0.5) / shape.sides
    apothem = shape.radius * np.cos(np.pi / shape.sides)
    spaces = [(np.array([np.cos(a), np.sin(a), 0.0]), apothem) for a in mid]
    spaces.append((np.array([0.0, 0.0, 1.0]), shape.height / 2.0))
    spaces.append((np.array([0.0, 0.0, -1.0]), shape.height / 2.0))
    return spaces
