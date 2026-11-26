# SPDX-License-Identifier: GPL-3.0-or-later
"""3-D sketch of the pillar with the force on its top face and the selected slip system.

The pillar is drawn standing on its substrate, i.e. in the pillar frame of `core.stereo`
(top face up). The sample axes x, y, z of the analysis are shown in this picture: z is
the force on the top face, pointing up in tension and down in compression.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from matplotlib.colors import to_rgb, to_rgba
from matplotlib.patches import FancyArrowPatch
from mpl_toolkits.mplot3d import proj3d
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

from ..core import pillar, stereo
from ..core.schmid import Analysis, force_sign, force_tex
from .style import (
    ANGLE_COLOUR, BURGERS_COLOUR, LOAD_COLOUR, NORMAL_COLOUR, PILLAR_COLOUR, REFERENCE_COLOUR,
    SUBSTRATE_COLOUR, Selection, schmid_colour,
)

SHAPE = pillar.PillarShape(radius=1.0, height=3.0, sides=48)
SUBSTRATE_RADIUS = 2.3
_HIGHEST = 3.65                     # the force arrow is kept below this height (edge of the image)
DEFAULT_VIEW = (16.0, -62.0)        # elevation, azimuth of the camera (degrees)
_Z = np.array([0.0, 0.0, 1.0])
_LIGHT = np.array([-0.45, -0.89])   # horizontal direction towards the (fictitious) light


@dataclass
class PillarOptions:
    slip_amount: float = 0.0        # slip step, in units of the pillar radius
    view: tuple = DEFAULT_VIEW
    labels: bool = True


def _selected(analysis: Analysis, selection: Selection):
    """(result representing the plane, result of the full system) – each may be None."""
    if selection is None or selection.plane not in analysis.plane_keys():
        return None, None
    return analysis.best_on_plane(selection.plane), analysis.find(selection.plane, selection.direction)


def _pillar_rotation(analysis: Analysis, rotation: np.ndarray) -> np.ndarray:
    """Rotation crystal -> pillar frame (top face up) from the rotation crystal -> sample frame."""
    return stereo.to_pillar(force_sign(analysis.loading.sense)) @ rotation


def suggested_view(analysis: Analysis, rotation: np.ndarray, selection: Selection = None) -> tuple:
    """Camera (elevation, azimuth) from which the selected plane and direction are seen well.

    `rotation`: crystal -> sample frame. The camera looks about 65 deg away from the
    horizontal part of the upward plane normal, so that the angle theta is hardly
    foreshortened and the slip plane appears as an open ellipse; of the two possible
    sides the one showing the slip directions of this plane better (on average) is used.
    The view depends on the selected plane only - neither on the slip direction chosen
    in it, so that the plane does not seem to change when stepping through its slip
    directions, nor on the loading sense.
    """
    plane_result, _ = _selected(analysis, selection)
    if plane_result is None:
        return DEFAULT_VIEW
    rotation = _pillar_rotation(analysis, rotation)
    n = stereo.upper(rotation @ plane_result.n)
    if np.hypot(n[0], n[1]) < 1e-6:
        return DEFAULT_VIEW
    base = np.degrees(np.arctan2(n[1], n[0]))
    directions = [rotation @ result.b for result in analysis.on_plane(selection.plane)]

    def sideways(azimuth):
        a = np.radians(azimuth)
        return sum(abs(-np.sin(a) * b[0] + np.cos(a) * b[1]) for b in directions)

    candidates = sorted([base - 65.0, base + 65.0], key=lambda azimuth: -round(sideways(azimuth), 9))
    azimuth = (candidates[0] + 180.0) % 360.0 - 180.0
    return (DEFAULT_VIEW[0], float(azimuth))


def draw_pillar(fig, analysis: Analysis, rotation: np.ndarray, selection: Selection = None,
                options: PillarOptions = None):
    """Draw the pillar sketch into `fig` (cleared first) and return the 3-D axes.

    `rotation`: crystal -> sample frame, the same matrix as for the stereographic projection.
    """
    selection = selection or Selection()
    options = options or PillarOptions()
    lattice = analysis.lattice
    tension = force_sign(analysis.loading.sense) > 0
    # everything below is in the pillar frame, in which the picture is drawn (top face up)
    to_pillar = stereo.to_pillar(force_sign(analysis.loading.sense))
    rotation = to_pillar @ rotation
    force = to_pillar @ _Z                                 # force on the top face = sample axis z
    half = SHAPE.height / 2.0
    plane_result, system_result = _selected(analysis, selection)
    shown = system_result or plane_result

    fig.clear()
    ax = fig.add_axes([0.0, 0.0, 1.0, 0.94], projection="3d", computed_zorder=False)
    ax.set_proj_type("ortho")
    ax.view_init(elev=options.view[0], azim=options.view[1])
    ax.set_axis_off()
    azimuth = np.radians(options.view[1])
    right = np.array([-np.sin(azimuth), np.cos(azimuth), 0.0])     # towards the right of the image

    # plane normal and slip direction of the block carrying the top face: both point into the
    # hemisphere of the force, i.e. upwards in tension and downwards in compression
    n = rotation @ shown.n if shown is not None else None
    b = rotation @ system_result.b if system_result is not None else None

    # ---- crystal blocks
    shift = np.zeros(3)
    if shown is None:
        blocks = [(pillar.prism_faces(SHAPE), np.zeros(3))]
        alpha = 0.95
    else:
        resting, loaded = pillar.blocks(n, SHAPE)
        if b is not None and options.slip_amount > 0:
            shift = pillar.slip_displacement(b, options.slip_amount)
        else:
            loaded = {**loaded, "cut": []}         # one common cut face is enough
        blocks = [(resting, np.zeros(3)), (pillar.translate(loaded, shift), shift)]
        alpha = 0.42
    top = half + shift[2]                          # height of the (displaced) top face

    polygons, colours, outlines = [], [], []
    for block, offset in blocks:
        for kind, group in block.items():
            for polygon in group:
                polygons.append(polygon)
                if kind == "cut":
                    colours.append(to_rgba(schmid_colour(shown.m), 0.85))
                elif kind == "side":
                    colours.append(_shaded(PILLAR_COLOUR, polygon.mean(axis=0) - offset, alpha))
                else:
                    colours.append(to_rgba(PILLAR_COLOUR, min(1.0, alpha + 0.2)))
                if kind != "side":
                    outlines.append(np.vstack([polygon, polygon[:1]]))

    substrate = _disc(SUBSTRATE_RADIUS, -half)
    looking_down = options.view[0] >= 0
    ax.add_collection3d(Poly3DCollection(
        [substrate], facecolors=[to_rgba(SUBSTRATE_COLOUR, 0.9)], edgecolors="#b5bac2",
        linewidths=0.6, zorder=1 if looking_down else 5))
    ax.add_collection3d(Poly3DCollection(polygons, facecolors=colours, edgecolors="none", zorder=3))
    # autolim=False: the outlines have different numbers of points when the plane leaves through
    # the top face, which the automatic scaling cannot handle; the limits are set below anyway
    ax.add_collection3d(Line3DCollection(outlines, colors="#4c535d", linewidths=0.9, zorder=4),
                        autolim=False)

    # ---- pillar axis and the force on the top face; the force is the sample axis z
    centre = np.array([0.0, 0.0, min(top + 1.0, _HIGHEST - 0.45)])     # middle of the force arrow
    ax.plot([0, 0], [0, 0], [-half - 0.35, centre[2] + 0.5], color=LOAD_COLOUR, lw=0.9,
            ls=(0, (7, 3, 1.5, 3)), zorder=6)
    arrow_3d(ax, centre - 0.45 * force, 0.9 * force, LOAD_COLOUR, lw=3.2)
    if options.labels:
        ax.text(*(0.16 * right + centre), force_tex(lattice, analysis.loading, r"F \parallel z"),
                color=LOAD_COLOUR, fontsize=10, ha="left", va="center", zorder=10)

    # ---- sample axes x and y (the same as in the stereographic projection); with z along the
    #      force they form a right-handed frame, so that x is reversed in compression
    for name, direction in (("x", to_pillar @ [1.0, 0, 0]), ("y", to_pillar @ [0, 1.0, 0])):
        start = 1.18 * direction + [0, 0, -half]
        arrow_3d(ax, start, 0.85 * direction, REFERENCE_COLOUR, lw=1.4)
        ax.text(*(start + 1.02 * direction), name, color="#5d646f", fontsize=9, style="italic",
                ha="center", va="center", zorder=10)

    # ---- slip plane normal, slip direction and angles (theta and lambda are measured from the force)
    if shown is not None:
        reach = _reach(n)
        arrow_3d(ax, [0, 0, 0], reach * n, NORMAL_COLOUR, lw=2.2)
        _arc(ax, force, n, 0.70, ANGLE_COLOUR)
        if options.labels:
            # a normal (nearly) along the pillar axis is labelled beside the axis, not on it
            aside = -0.75 * right if abs(n[2]) > 0.97 else 0.0
            _tip_label(ax, reach * n + aside, n, right, f"$\\mathbf{{n}}$ {lattice.plane_tex(shown.plane)}",
                       NORMAL_COLOUR)
            ax.text(*(0.88 * _bisector(force, n)), r"$\theta$", color=ANGLE_COLOUR, fontsize=11,
                    ha="center", va="center", zorder=10)
    if system_result is not None:
        # b is the slip direction of the block carrying the top face
        reach = _reach(b, shift)
        arrow_3d(ax, shift, reach * b, BURGERS_COLOUR, lw=2.2)
        _arc(ax, force, b, 1.0, ANGLE_COLOUR, origin=shift)
        if options.labels:
            _tip_label(ax, shift + reach * b, b, right,
                       f"$\\mathbf{{b}}$ {lattice.direction_tex(system_result.direction)}", BURGERS_COLOUR)
            ax.text(*(shift + 1.18 * _bisector(force, b)), r"$\lambda$", color=ANGLE_COLOUR,
                    fontsize=11, ha="center", va="center", zorder=10)
        if options.slip_amount <= 0 and system_result.m > 1e-9:
            _shear_arrows(ax, n, b)

    ax.set_xlim(-2.3, 2.3)
    ax.set_ylim(-2.3, 2.3)
    ax.set_zlim(-1.45, 3.15)
    ax.set_box_aspect((1, 1, 1), zoom=1.30)

    title = "Sample " + ("tension" if tension else "compression")
    if system_result is not None:
        title += (f":  {lattice.plane_tex(system_result.plane)}{lattice.direction_tex(system_result.direction)}"
                  f",  $m$ = {system_result.m:.4f}")
    elif plane_result is not None:
        title += f":  plane {lattice.plane_tex(plane_result.plane)}"
    fig.suptitle(title, fontsize=10, y=0.975)
    return ax


# --------------------------------------------------------------------------- helpers
def _disc(radius: float, z: float, sides: int = 72) -> np.ndarray:
    t = 2.0 * np.pi * np.arange(sides) / sides
    return np.column_stack([radius * np.cos(t), radius * np.sin(t), np.full(sides, z)])


def _shaded(colour, centre, alpha):
    """Colour of a side facet (outward direction = horizontal part of `centre`), lit from _LIGHT."""
    horizontal = np.asarray(centre[:2], dtype=float)
    norm = np.linalg.norm(horizontal)
    lit = float(horizontal @ _LIGHT) / norm if norm > 1e-9 else 0.0
    rgb = np.clip(np.array(to_rgb(colour)) * (0.86 + 0.16 * lit), 0.0, 1.0)
    return (*rgb, alpha)


class _Arrow3D(FancyArrowPatch):
    """Arrow between two 3-D points whose head always faces the viewer."""

    def __init__(self, start, end, **kwargs):
        super().__init__((0, 0), (0, 0), **kwargs)
        self._ends = np.array([start, end], dtype=float)

    def do_3d_projection(self, renderer=None):
        xs, ys, zs = proj3d.proj_transform(*self._ends.T, self.axes.M)
        self.set_positions((xs[0], ys[0]), (xs[1], ys[1]))
        return float(np.min(zs))


def arrow_3d(ax, start, vector, colour, lw=2.0):
    """Arrow from `start` along `vector` in a 3-D axes (also used by the documentation figures)."""
    start = np.asarray(start, dtype=float)
    ax.add_artist(_Arrow3D(start, start + np.asarray(vector, dtype=float), color=colour, lw=lw,
                           arrowstyle="-|>", mutation_scale=7 + 4 * lw, shrinkA=0, shrinkB=0,
                           zorder=8))


def _arc(ax, start, end, radius, colour, origin=(0.0, 0.0, 0.0)):
    points = np.asarray(origin) + radius * stereo.arc(start, end)
    ax.plot(points[:, 0], points[:, 1], points[:, 2], color=colour, lw=1.6, zorder=7)


def _bisector(a, b) -> np.ndarray:
    middle = np.asarray(a, dtype=float) + np.asarray(b, dtype=float)
    norm = np.linalg.norm(middle)
    return middle / norm if norm > 1e-9 else np.asarray(a, dtype=float)


def _reach(vector, origin=(0.0, 0.0, 0.0), length: float = 1.75) -> float:
    """Length of the arrow from `origin` along the unit `vector`; it ends above the substrate."""
    if vector[2] >= 0:
        return length
    return min(length, (origin[2] + SHAPE.height / 2.0 - 0.1) / -vector[2])


def _tip_label(ax, tip, vector, right, text, colour):
    """Label at the tip of an arrow along `vector`: beyond the tip, or beside it if the arrow points down."""
    if vector[2] >= 0:
        position, align = tip + 0.19 * vector, "center"
    else:
        sideways = 1.0 if vector @ right >= 0 else -1.0
        position, align = tip + 0.10 * vector + 0.10 * sideways * right, "left" if sideways > 0 else "right"
    ax.text(*position, text, color=colour, fontsize=10, ha=align, va="center", zorder=10)


def _shear_arrows(ax, n, b):
    """Pair of arrows showing the sense of shear across the slip plane (resolved shear stress)."""
    side = np.cross(n, b)
    side = side / np.linalg.norm(side)
    loaded = 1.0 if n[2] >= 0 else -1.0            # side of the plane on which the top face lies
    for face in (1.0, -1.0):                       # the block carrying the top face moves along b
        direction = face * loaded * b
        start = 0.62 * side + face * 0.13 * n - 0.36 * direction
        arrow_3d(ax, start, 0.72 * direction, NORMAL_COLOUR, lw=1.3)
    ax.text(*(0.62 * side - 0.55 * b), r"$\tau$", color=NORMAL_COLOUR, fontsize=10, ha="center",
            va="center", zorder=10)
