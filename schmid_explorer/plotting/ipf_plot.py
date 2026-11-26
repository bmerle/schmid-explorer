# SPDX-License-Identifier: GPL-3.0-or-later
"""Inverse pole figure: the loading axis in the standard triangle of the crystal."""

from __future__ import annotations

import numpy as np

from ..core import inverse_pole_figure, orientation_map, stereo
from ..core.schmid import Analysis, load_axis, load_axis_tex
from .style import LOAD_COLOUR

TRIANGLE_COLOUR = "#e9edf3"


def draw_ipf(fig, analysis: Analysis):
    """Draw the standard triangle with the loading axis into `fig` (cleared first); returns the axes.

    Data coordinates of the axes are the stereographic (X, Y) in the frame
    `inverse_pole_figure.triangle_frame`.
    """
    lattice = analysis.lattice
    rotation = inverse_pole_figure.triangle_frame(lattice)
    corners = orientation_map.fundamental_zone(lattice)
    vectors = [rotation @ lattice.direction_vector(c) for c in corners]

    fig.clear()
    ax = fig.add_axes([0.19, 0.06, 0.58, 0.86])
    ax.axis("off")

    # ---- standard triangle and its corners
    outline = np.vstack([stereo.project(stereo.arc(start, end))
                         for start, end in zip(vectors, vectors[1:] + vectors[:1])])
    ax.fill(outline[:, 0], outline[:, 1], facecolor=TRIANGLE_COLOUR, edgecolor="black", lw=1.2,
            joinstyle="round")
    ax.margins(0.03)
    ax.set_aspect("equal", adjustable="datalim")       # the triangle fills the axes at any figure shape
    for index, (corner, vector) in enumerate(zip(corners, vectors)):
        side = -1 if index == 0 else 1             # first corner on the left, the others on the right
        ax.annotate(lattice.direction_tex(corner), stereo.project(vector), xytext=(9 * side, 0),
                    textcoords="offset points", ha="right" if side < 0 else "left", va="center",
                    fontsize=8.5, color="black")

    # ---- loading axis: its symmetry-equivalent direction inside the triangle
    reduced = inverse_pole_figure.reduce_loading(lattice, analysis.loading)
    xy = inverse_pole_figure.triangle_point(lattice, load_axis(lattice, reduced))
    ax.scatter(*xy, s=120, marker="*", color=LOAD_COLOUR, edgecolors="white", linewidths=0.7,
               zorder=5, clip_on=False)
    # the text stands in the corner above the edge from the first to the third corner, which is empty
    text = f"$\\bigstar$ loading axis {load_axis_tex(lattice, analysis.loading)}"
    if reduced.indices != tuple(analysis.loading.indices):
        text += f"\nequivalent to {load_axis_tex(lattice, reduced)}"
    fig.text(0.03, 0.95, text, ha="left", va="top", fontsize=8.5, linespacing=1.35)
    return ax
