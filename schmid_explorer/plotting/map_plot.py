# SPDX-License-Identifier: GPL-3.0-or-later
"""Orientation map: highest Schmid factor (or lowest yield stress) versus loading axis."""

from __future__ import annotations

import numpy as np
from matplotlib.patches import Circle
from matplotlib.patheffects import withStroke

from ..core import orientation_map, stereo
from ..core.schmid import Analysis, load_axis_tex
from .style import SCHMID_CMAP, SCHMID_NORM

CONTOUR_LEVELS = (0.30, 0.35, 0.40, 0.45, 0.49)


def draw_orientation_map(fig, analysis: Analysis, pixels: int = 241):
    """Draw the map into `fig` (cleared first) and return the axes of the projection.

    Data coordinates of the axes are the stereographic (X, Y) of the standard
    projection; use `orientation_map.standard_frame` to convert a click to a crystal
    direction.
    """
    lattice = analysis.lattice
    rotation = orientation_map.standard_frame(lattice)
    x, y, values = orientation_map.schmid_map(analysis, pixels)

    fig.clear()
    ax = fig.add_axes([0.04, 0.05, 0.78, 0.84])
    cax = fig.add_axes([0.85, 0.17, 0.03, 0.60])
    ax.set_aspect("equal")
    ax.set_xlim(-1.14, 1.14)
    ax.set_ylim(-1.14, 1.14)
    ax.axis("off")

    clip = Circle((0, 0), 1.0, transform=ax.transData)
    finite = np.isfinite(values)
    if analysis.use_crss:
        low = float(np.nanmin(np.where(finite, values, np.nan))) if finite.any() else 1.0
        high = min(float(np.nanmax(np.where(finite, values, np.nan))), 4.0 * low) if finite.any() else 2.0
        image = ax.imshow(np.where(finite, values, np.nan), extent=(-1, 1, -1, 1), origin="lower",
                          cmap="viridis_r", vmin=low, vmax=max(high, low * 1.01),
                          interpolation="bilinear")
        label = r"lowest yield stress $\sigma_y = \tau_{CRSS}/m$ (units of CRSS)"
    else:
        image = ax.imshow(values, extent=(-1, 1, -1, 1), origin="lower", cmap=SCHMID_CMAP,
                          norm=SCHMID_NORM, interpolation="bilinear")
        contours = ax.contour(x, y, values, levels=CONTOUR_LEVELS, colors="white", linewidths=0.6)
        contours.set_clip_path(clip)
        label = "highest Schmid factor $m$"
    image.set_clip_path(clip)
    ax.add_patch(Circle((0, 0), 1.0, fill=False, lw=1.3, color="black", zorder=4))
    bar = fig.colorbar(image, cax=cax)
    bar.set_label(label)
    if not analysis.use_crss:
        for level in CONTOUR_LEVELS:               # the white contour lines of the map
            bar.ax.axhline(level, color="white", lw=0.8)

    # ---- standard triangle and its corners
    corners = orientation_map.fundamental_zone(lattice)
    vectors = [rotation @ lattice.direction_vector(c) for c in corners]
    for start, end in zip(vectors, vectors[1:] + vectors[:1]):
        edge = stereo.project(stereo.arc(start, end))
        ax.plot(edge[:, 0], edge[:, 1], color="white", lw=1.5, zorder=5,
                path_effects=[withStroke(linewidth=3.0, foreground="black")])
    centre = np.mean([stereo.project(v) for v in vectors], axis=0)
    for corner, vector in zip(corners, vectors):
        xy = stereo.project(vector)
        away = xy - centre
        away = away / np.linalg.norm(away)
        ax.annotate(lattice.direction_tex(corner), xy, xytext=(15 * away[0], 12 * away[1]),
                    textcoords="offset points", ha="center", va="center", fontsize=8.5,
                    color="black", zorder=8,
                    bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))

    # ---- current loading axis
    axis = stereo.upper(rotation @ analysis.axis)
    xy = stereo.project(axis)
    ax.scatter(*xy, s=150, marker="*", color="white", edgecolors="black", linewidths=1.0, zorder=7)
    fig.suptitle(f"{analysis.structure.key}: orientation map, loading axis "
                 f"{load_axis_tex(lattice, analysis.loading)} ($\\bigstar$)", fontsize=10, y=0.965)
    return ax
