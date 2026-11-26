# SPDX-License-Identifier: GPL-3.0-or-later
"""Stereographic projection of the glide planes, coloured by Schmid factor.

The projection shows the hemisphere around the force on the top face (sample axis z,
towards the viewer, see `core.stereo`): the force is its centre. Plane normals and slip
directions are oriented into this hemisphere by the analysis, so that the angles theta
and lambda of a glide system can be read as the distances of its pole and of its slip
direction from the centre.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
from matplotlib import patheffects
from matplotlib.lines import Line2D
from matplotlib.patches import Circle

from ..core import stereo
from ..core.lattice import CUBIC
from ..core.schmid import TENSION, Analysis, force_tex, load_axis_tex
from .style import (
    ANGLE_COLOUR, PRIMARY_COLOUR, REFERENCE_COLOUR, Selection, schmid_colour, schmid_mappable,
)

LIMIT = 1.17                        # half width of the plotted area (projection units)


@dataclass
class StereoOptions:
    traces: bool = False            # great circles of all glide planes
    reference_poles: bool = True    # low-index crystal directions for orientation
    wulff_net: bool = False
    circle_45: bool = False         # cone of directions at 45 deg from the force
    labels: bool = True


@dataclass
class StereoScene:
    """Positions of the clickable markers, for hit testing by the GUI."""

    poles: list = field(default_factory=list)        # (xy, plane key)
    directions: list = field(default_factory=list)   # (xy, direction key)

    def hit(self, x: float, y: float, radius: float = 0.05):
        """('direction' | 'plane', key) of the marker closest to (x, y), or None."""
        for kind, markers in (("direction", self.directions), ("plane", self.poles)):
            best, best_distance = None, radius
            for xy, key in markers:
                distance = float(np.hypot(xy[0] - x, xy[1] - y))
                if distance <= best_distance:
                    best, best_distance = key, distance
            if best is not None:
                return kind, best
        return None


def draw_stereo(fig, analysis: Analysis, rotation: np.ndarray, selection: Selection = None,
                options: StereoOptions = None) -> StereoScene:
    """Draw the projection into `fig` (cleared first).

    `rotation`: crystal -> sample frame (z along the force), from `stereo.sample_frame`.
    """
    selection = selection or Selection()
    options = options or StereoOptions()
    lattice = analysis.lattice
    scene = StereoScene()

    fig.clear()
    ax = fig.add_axes([0.03, 0.05, 0.80, 0.86])
    cax = fig.add_axes([0.86, 0.17, 0.028, 0.62])
    ax.set_aspect("equal")
    ax.set_xlim(-LIMIT, LIMIT)
    ax.set_ylim(-LIMIT, LIMIT)
    ax.axis("off")
    labels = _LabelPlacer(ax)                       # labels are placed at the end, by priority
    occupied = []                                   # positions already carrying a marker

    if options.wulff_net:
        for line in stereo.wulff_net():
            ax.plot(line[:, 0], line[:, 1], color=REFERENCE_COLOUR, lw=0.35, alpha=0.6, zorder=1)
    ax.add_patch(Circle((0, 0), 1.0, fill=False, lw=1.3, color="black", zorder=2))
    if options.circle_45:
        ring = stereo.small_circle_about_axis(45.0)
        ax.plot(ring[:, 0], ring[:, 1], color=ANGLE_COLOUR, lw=1.0, ls="--", zorder=2)
        labels.request(6, "45°", ring[len(ring) // 8], towards=(1, 1), size=8, colour=ANGLE_COLOUR,
                       gap=2.0, optional=True, leader=False)
    for label, position, offset in (("x", (1.0, 0.0), (9, -8)), ("y", (0.0, 1.0), (10, 5))):
        ax.annotate(label, position, xytext=offset, textcoords="offset points", ha="center",
                    va="center", fontsize=9, style="italic", color=REFERENCE_COLOUR)
        labels.block(np.array(position) + labels.unit * np.array(offset), 5.0)
    ax.plot([1.0, 1.035], [0, 0], color="black", lw=1.0, zorder=2)
    ax.plot([0, 0], [1.0, 1.035], color="black", lw=1.0, zorder=2)

    plane_keys = analysis.plane_keys()
    selected = selection.plane if selection.plane in plane_keys else None

    # ---- glide-plane poles (and optionally all traces)
    for key in reversed(plane_keys):                # best plane drawn last = on top
        best = analysis.best_on_plane(key)
        pole = rotation @ best.n
        colour = schmid_colour(best.m)
        dimmed = selected is not None and key != selected
        if options.traces and not dimmed:
            trace = stereo.great_circle(pole)
            ax.plot(trace[:, 0], trace[:, 1], color=colour, lw=1.0, alpha=0.9, zorder=3)
        primary = any(r.primary for r in analysis.on_plane(key))
        for sign, xy in zip((1, -1), stereo.plot_points(pole)):
            if primary:
                ax.scatter(*xy, s=190, facecolors="none", edgecolors=PRIMARY_COLOUR,
                           linewidths=1.6, alpha=0.35 if dimmed else 1.0, zorder=5)
            ax.scatter(*xy, s=85, color=colour, edgecolors="black", linewidths=0.8,
                       alpha=0.35 if dimmed else 1.0, zorder=6)
            scene.poles.append((xy, key))
            occupied.append(xy)
            reach = 8.3 if key == selected else 7.2 if primary else 5.0      # marker radius, points
            labels.block(xy, reach)
            # labels of the selected plane and of the planes activated first are always shown,
            # the others in the order of their Schmid factor as long as there is room
            needed = not dimmed and (primary or key == selected)
            priority = 3 if needed else (7 if dimmed else 5) + 0.001 * plane_keys.index(key)
            labels.request(priority, lattice.plane_tex(tuple(sign * i for i in best.plane)), xy,
                           towards=_outwards(xy), size=8 if dimmed else 9,
                           colour="#9aa0a6" if dimmed else "black", gap=1.25 * reach, optional=not needed)

    # ---- selected plane: trace and glide directions
    if selected is not None:
        best = analysis.best_on_plane(selected)
        pole = rotation @ best.n
        trace = stereo.great_circle(pole)
        ax.plot(trace[:, 0], trace[:, 1], color="black", lw=1.8, zorder=4)
        labels.block_line(trace)
        for xy in stereo.plot_points(pole):
            ax.scatter(*xy, s=260, facecolors="none", edgecolors="black", linewidths=2.0, zorder=7)
        for result in analysis.on_plane(selected):
            chosen = result.direction_key == selection.direction
            points = stereo.plot_points(rotation @ result.b)
            for sign, xy in zip((1, -1), points):   # second point: other end of a line on the equator
                ax.scatter(*xy, s=95, marker="s", color=schmid_colour(result.m),
                           edgecolors="black", linewidths=2.2 if chosen else 0.8, zorder=8)
                scene.directions.append((xy, result.direction_key))
                occupied.append(xy)
                labels.block(xy, 5.2)
                labels.request(1 if chosen else 2, lattice.direction_tex(tuple(sign * i for i in result.direction)),
                               xy, towards=-_outwards(xy), size=9, colour="black", gap=6.8)
            if chosen:
                # theta and lambda: from the force in the centre to the pole and to the slip direction
                for end, text in ((stereo.plot_points(pole)[0], rf"$\theta$ = {result.theta_deg:.1f}°"),
                                  (points[0], rf"$\lambda$ = {result.lambda_deg:.1f}°")):
                    ax.plot([0, end[0]], [0, end[1]], color=ANGLE_COLOUR, lw=1.4, zorder=4)
                    labels.block_line(np.linspace((0.0, 0.0), end, 25))
                    # preferred position: the quadrant beside the line, on its right-hand side
                    across = np.sign([end[1], -end[0]]) if np.hypot(*end) > 1e-6 else np.array([1.0, 0.0])
                    along = np.outer((0.55, 0.40, 0.70, 0.28), end)
                    labels.request(0, text, along, towards=across if across[0] >= 0 else -across,
                                   size=8.5, colour=ANGLE_COLOUR, gap=3.0, leader=False)

    # ---- force on the top face (sample axis z) in the centre, pointing towards the viewer
    tension = analysis.loading.sense == TENSION
    halo = [patheffects.withStroke(linewidth=3.4, foreground="white")]
    ax.scatter(0, 0, s=150, marker="o", facecolors="none", edgecolors="black", linewidths=1.4,
               path_effects=halo, zorder=9)
    ax.scatter(0, 0, s=22, marker="o", color="black", linewidths=1.5, path_effects=halo, zorder=9)
    labels.block((0.0, 0.0), 6.6)
    labels.request(4, force_tex(lattice, analysis.loading), (0.0, 0.0), towards=(1, -1), size=9,
                   colour="black", gap=7.6, weight="bold")

    # ---- reference poles
    if options.reference_poles:
        _reference_poles(ax, analysis, rotation, occupied, labels)
    if options.labels:
        labels.place_all()

    # ---- colour bar, legend, title
    bar = fig.colorbar(schmid_mappable(), cax=cax)
    bar.set_label("Schmid factor $m$")
    bar.set_ticks([0, 0.1, 0.2, 0.3, 0.4, 0.5])
    force = (Line2D([], [], marker="o", ls="", markerfacecolor="none", markeredgecolor="black",
                    markeredgewidth=1.2, markersize=9),
             Line2D([], [], marker="o", ls="", color="black", markeredgewidth=1.2, markersize=3.2))
    entries = [                                      # the legend is filled column by column
        (Line2D([], [], marker="o", ls="", markerfacecolor=schmid_colour(0.35),
                markeredgecolor="black", markersize=7), "glide-plane pole"),
        (Line2D([], [], marker="o", ls="", markerfacecolor="none", markeredgecolor=PRIMARY_COLOUR,
                markeredgewidth=1.5, markersize=10), "activated first"),
        (force, r"force $F \parallel z$, towards the viewer: view "
                + ("onto the top face" if tension else "from below the pillar")),
        (Line2D([], [], marker="s", ls="", markerfacecolor=schmid_colour(0.35),
                markeredgecolor="black", markersize=7), "glide direction of the selected plane"),
    ]
    fig.legend(handles=[handle for handle, _text in entries], labels=[text for _handle, text in entries],
               loc="lower left", bbox_to_anchor=(0.01, 0.0), ncols=2, fontsize=7.5, frameon=False,
               handletextpad=0.2, columnspacing=1.4, labelspacing=0.35)
    fig.suptitle(f"{analysis.structure.key}, loading axis {load_axis_tex(lattice, analysis.loading)}, "
                 f"{analysis.loading.sense}: {force_tex(lattice, analysis.loading, 'F')}",
                 fontsize=10, y=0.975)
    return scene


# --------------------------------------------------------------------------- helpers
def _outwards(xy) -> np.ndarray:
    """Unit vector from the centre through xy (upwards for a point in the centre)."""
    radius = float(np.hypot(*xy))
    return np.asarray(xy) / radius if radius >= 0.08 else np.array([0.0, 1.0])


def _text_size(text: str, size: float) -> tuple:
    """Approximate (width, height) of a label in points; mathtext commands count as one letter."""
    plain = re.sub(r"\\bar\{(\d+)\}", r"\1", text)
    plain = re.sub(r"\\[a-zA-Z]+ ?", "x", plain)
    plain = re.sub(r"[${}\\,]", "", plain)
    wide = sum(character.isalnum() for character in plain)
    return size * (0.64 * wide + 0.38 * (len(plain) - wide)), 1.35 * size


class _LabelPlacer:
    """Greedy label placement.

    Markers and lines are registered as blocked boxes; the labels are then placed in the order
    of their priority, each at the first of eight positions around its anchor that is free
    (failing that, a little further away; failing that, where it overlaps least).
    """

    COMPASS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]

    def __init__(self, ax):
        self.ax = ax
        box = ax.bbox
        self.unit = 2 * LIMIT * ax.figure.dpi / (72.0 * min(box.width, box.height))   # projection units per point
        self.boxes = []
        self.requests = []

    def block(self, xy, points: float):
        half = points * self.unit
        self.boxes.append((xy[0] - half, xy[1] - half, xy[0] + half, xy[1] + half))

    def block_line(self, line, points: float = 1.5):
        for xy in line:
            self.block(xy, points)

    def request(self, priority: float, text: str, xy, towards, **style):
        """`xy`: anchor of the label, or several alternative anchors (the first one is preferred)."""
        self.requests.append((priority, len(self.requests), text, np.atleast_2d(np.asarray(xy, dtype=float)),
                              np.asarray(towards, dtype=float), style))

    def place_all(self):
        for _priority, _order, text, anchors, towards, style in sorted(self.requests, key=lambda r: r[:2]):
            self._place(text, anchors, towards, **style)

    def _overlap(self, box) -> float:
        """Area shared with the blocked boxes (infinite outside the plotted area)."""
        if box[0] < -LIMIT - 0.08 or box[2] > LIMIT + 0.04 or box[1] < -LIMIT or box[3] > LIMIT:
            return np.inf
        return sum(max(0.0, min(box[2], other[2]) - max(box[0], other[0]))
                   * max(0.0, min(box[3], other[3]) - max(box[1], other[1])) for other in self.boxes)

    def _place(self, text, anchors, towards, size, colour, gap, weight="normal", optional=False,
               leader=True):
        width, height = (value * self.unit for value in _text_size(text, size))
        start = int(np.round(np.arctan2(towards[1], towards[0]) / (np.pi / 4)))
        best, least = None, np.inf
        for distance in (gap * self.unit, (gap + 8.0) * self.unit):
            for xy in anchors:
                for step in (0, 1, -1, 2, -2, 3, -3, 4):
                    ux, uy = self.COMPASS[(start + step) % 8]
                    reach = distance * (0.85 if ux and uy else 1.0)     # stays outside the marker's own box
                    cx = xy[0] + ux * (reach + width / 2)
                    cy = xy[1] + uy * (reach + height / 2)
                    box = (cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2)
                    overlap = self._overlap(box)
                    if overlap < least:
                        best, least = (cx, cy, box, xy, distance > gap * self.unit), overlap
                    if overlap == 0.0:
                        break
                if least == 0.0:
                    break
            if least == 0.0:
                break
        if best is None or (optional and least > 0.0):
            return                                  # no room: optional labels are left out
        cx, cy, box, xy, far = best
        self.boxes.append(box)
        self.ax.text(cx, cy, text, ha="center", va="center", fontsize=size, color=colour,
                     weight=weight, zorder=10)
        if far and leader:                          # thin line from the marker to its distant label
            end = (min(max(xy[0], box[0]), box[2]), min(max(xy[1], box[1]), box[3]))
            self.ax.plot([xy[0], end[0]], [xy[1], end[1]], color=colour, lw=0.6, zorder=5)


def _reference_poles(ax, analysis, rotation, occupied, labels):
    """Low-index crystal directions as open grey symbols (skipped where a marker sits)."""
    from ..core.symmetry import equivalent_directions

    lattice = analysis.lattice
    if lattice.system == CUBIC:
        families = [((1, 0, 0), "s"), ((1, 1, 0), "d"), ((1, 1, 1), "^")]
    else:
        families = [((0, 0, 1), "h"), ((1, 0, 0), "d"), ((2, 1, 0), "d")]
    for seed, marker in families:
        for member in equivalent_directions(lattice, seed):
            vector = rotation @ lattice.direction_vector(member)
            signs = (1, -1) if abs(vector[2]) < 1e-9 else ((1,) if vector[2] > 0 else (-1,))
            for sign in signs:
                xy = stereo.project(sign * vector)
                if any(np.hypot(*(xy - other)) < 0.03 for other in occupied):
                    continue
                if np.hypot(*xy) < 0.03:
                    continue                    # the loading axis itself
                ax.scatter(*xy, s=34, marker=marker, facecolors="white",
                           edgecolors=REFERENCE_COLOUR, linewidths=0.9, zorder=3)
                labels.block(xy, 3.2)
                labels.request(8, lattice.direction_tex(tuple(sign * i for i in member)), xy,
                               towards=_outwards(xy), size=7, colour=REFERENCE_COLOUR, gap=4.5,
                               optional=True)
