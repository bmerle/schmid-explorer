# SPDX-License-Identifier: GPL-3.0-or-later
"""Pillar frame, sample frame and stereographic projection.

Pillar frame (how the crystal sits in the pillar)
-------------------------------------------------
z_p : loading axis l = outward normal of the top face (from the substrate to the top face)
y_p : chosen such that a crystal reference direction (cubic [100], hexagonal
      [2 -1 -1 0]) lies on the -y_p side, the "south" of the usual standard projections;
      an azimuth angle turns the crystal about z_p (counter-clockwise seen from above)
x_p : y_p x z_p (right-handed frame)

Sample frame x, y, z (frame of the Schmid analysis and of the projection)
-------------------------------------------------------------------------
z points along the force acting on the top face, f = sign * l:

    tension     (sign = +1):  x = x_p,   y = y_p,  z = z_p    (the pillar frame)
    compression (sign = -1):  x = -x_p,  y = y_p,  z = -z_p   (half turn about y)

In compression z points down, into the pillar. The half turn keeps the frame
right-handed and leaves the crystal where it is: reversing the force turns the frame of
reference, not the crystal in the pillar.

`pillar_frame` and `sample_frame` return the rotation matrix R with  v_frame = R @ v_crystal.

Stereographic projection
------------------------
The hemisphere z >= 0 of the sample frame, i.e. the hemisphere around the force, is
projected from the opposite pole (0, 0, -1) onto the equatorial plane:

    X = x / (1 + z),    Y = y / (1 + z)

X to the right, Y upwards, z towards the viewer. The force is the centre of the
projection; a direction at the angle rho from the force plots at the distance
tan(rho / 2) from the centre, and the primitive circle (rho = 90 deg) has radius 1.
In tension the viewer looks onto the top face of the pillar, in compression at the
pillar from below (from the side of the substrate), against the force in both cases.

Plane normals and slip directions are oriented into the hemisphere of the force (see
`schmid`) and are therefore all plotted in this one hemisphere (`plot_points`).
"""

from __future__ import annotations

from math import cos, radians, sin

import numpy as np

from .lattice import CUBIC, Lattice

_PARALLEL = 0.999
HALF_TURN = np.diag([-1.0, 1.0, -1.0])     # half turn about y: pillar frame <-> sample frame in compression


def reference_directions(lattice: Lattice) -> list:
    """Candidate crystal reference directions (three Miller indices) for the azimuth."""
    if lattice.system == CUBIC:
        return [(1, 0, 0), (0, 1, 0)]
    return [(1, 0, 0), (0, 0, 1)]      # [2 -1 -1 0] and [0 0 0 1]


def sample_frame(lattice: Lattice, axis: np.ndarray, azimuth_deg: float = 0.0, sign: int = 1):
    """Rotation matrix crystal -> sample frame (z along the force) and the reference direction.

    `axis` is the loading axis l and `sign` the sign of the force on the top face,
    f = sign * l (`schmid.force_sign`): +1 in tension, -1 in compression.
    """
    rotation, reference = pillar_frame(lattice, axis, azimuth_deg)
    return to_pillar(sign) @ rotation, reference


def to_pillar(sign: int) -> np.ndarray:
    """Matrix taking sample coordinates to pillar coordinates (and back: it is its own inverse)."""
    return HALF_TURN if sign < 0 else np.eye(3)


def pillar_frame(lattice: Lattice, axis: np.ndarray, azimuth_deg: float = 0.0):
    """Rotation matrix crystal -> pillar frame (z along `axis`) and the reference direction used."""
    z = np.asarray(axis, dtype=float)
    z = z / np.linalg.norm(z)
    for reference in reference_directions(lattice):
        r = lattice.direction_vector(reference)
        if abs(np.dot(r, z)) < _PARALLEL:
            break
    south = r - np.dot(r, z) * z
    y = -south / np.linalg.norm(south)
    x = np.cross(y, z)
    rotation = np.vstack([x, y, z])
    return rotation_z(azimuth_deg) @ rotation, reference


def rotation_z(angle_deg: float) -> np.ndarray:
    """Counter-clockwise rotation about z by the given angle."""
    c, s = cos(radians(angle_deg)), sin(radians(angle_deg))
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def upper(vector) -> np.ndarray:
    """Antipode-fold a vector (or an array of vectors) into the hemisphere z >= 0."""
    v = np.asarray(vector, dtype=float)
    return np.where(v[..., 2:3] < 0, -v, v)


def project(vector) -> np.ndarray:
    """Stereographic projection of unit vector(s) with z >= 0 -> (X, Y)."""
    v = np.asarray(vector, dtype=float)
    return v[..., :2] / (1.0 + v[..., 2:3])


def inverse_project(xy) -> np.ndarray:
    """Unit vector(s) belonging to the projected point(s) (X, Y)."""
    p = np.asarray(xy, dtype=float)
    r2 = np.sum(p * p, axis=-1, keepdims=True)
    return np.concatenate([2.0 * p, 1.0 - r2], axis=-1) / (1.0 + r2)


def plot_points(vector, tolerance: float = 1e-9) -> np.ndarray:
    """Projected point(s) of a pole or direction: its end with z >= 0, both ends on the equator.

    For a vector on the equator the first point is the vector itself, the second one
    its antipode.
    """
    v = np.asarray(vector, dtype=float)
    if abs(v[2]) < tolerance:
        return np.array([project(v), project(-v)])
    return np.array([project(upper(v))])


def great_circle(pole, points: int = 181) -> np.ndarray:
    """Projected trace of the plane normal to `pole`: the half lying in the hemisphere z >= 0."""
    p = np.asarray(pole, dtype=float)
    p = p / np.linalg.norm(p)
    z = np.array([0.0, 0.0, 1.0])
    e1 = np.cross(z, p)
    if np.linalg.norm(e1) < 1e-9:              # plane = equatorial plane
        t = np.linspace(0.0, 2.0 * np.pi, 2 * points - 1)
        return np.column_stack([np.cos(t), np.sin(t)])
    e1 = e1 / np.linalg.norm(e1)
    e2 = np.cross(p, e1)
    if e2[2] < 0:
        e2 = -e2
    t = np.linspace(0.0, np.pi, points)
    circle = np.outer(np.cos(t), e1) + np.outer(np.sin(t), e2)
    return project(circle)


def small_circle_about_axis(angle_deg: float, points: int = 181) -> np.ndarray:
    """Projected cone of directions at a fixed angle from z, the force (a circle)."""
    radius = np.tan(radians(angle_deg) / 2.0)
    t = np.linspace(0.0, 2.0 * np.pi, points)
    return radius * np.column_stack([np.cos(t), np.sin(t)])


def wulff_net(step_deg: float = 10.0, points: int = 91) -> list:
    """Polylines of a Wulff net (meridians and parallels) with poles at north / south."""
    lines = []
    t = np.linspace(0.0, np.pi, points)
    for alpha in np.radians(np.arange(-90.0 + step_deg, 90.0, step_deg)):
        meridian = np.column_stack(
            [np.sin(t) * np.sin(alpha), np.cos(t), np.sin(t) * np.cos(alpha)])
        lines.append(project(meridian))
    s = np.linspace(-np.pi / 2.0, np.pi / 2.0, points)
    for beta in np.radians(np.arange(step_deg, 180.0, step_deg)):
        parallel = np.column_stack(
            [np.sin(beta) * np.sin(s), np.full_like(s, np.cos(beta)), np.sin(beta) * np.cos(s)])
        lines.append(project(parallel))
    return lines


def arc(start, end, points: int = 40) -> np.ndarray:
    """Unit vectors along the shorter great-circle arc from `start` to `end`."""
    a = np.asarray(start, dtype=float)
    b = np.asarray(end, dtype=float)
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    omega = np.arccos(np.clip(np.dot(a, b), -1.0, 1.0))
    if omega < 1e-9:
        return np.repeat(a[None, :], points, axis=0)
    t = np.linspace(0.0, 1.0, points)[:, None]
    return (np.sin((1.0 - t) * omega) * a + np.sin(t * omega) * b) / np.sin(omega)
