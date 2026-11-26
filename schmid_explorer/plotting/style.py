# SPDX-License-Identifier: GPL-3.0-or-later
"""Colours and the Schmid-factor colour scale shared by all figures."""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib as mpl
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

SCHMID_CMAP = mpl.colormaps["viridis"]
SCHMID_NORM = Normalize(vmin=0.0, vmax=0.5)

NORMAL_COLOUR = "#9b0a45"      # plane normal n (crimson, as on the lecture slides)
BURGERS_COLOUR = "#1b4f9c"     # slip direction b
ANGLE_COLOUR = "#1f8a70"       # angles theta and lambda
LOAD_COLOUR = "#111111"        # loading axis and force
PRIMARY_COLOUR = "#d62728"     # ring around systems that are activated first
REFERENCE_COLOUR = "#8a8f98"   # reference poles, nets
PILLAR_COLOUR = "#c5cad3"
SUBSTRATE_COLOUR = "#e3e6ea"


def schmid_colour(m: float):
    """RGBA colour of a Schmid factor on the common 0 ... 0.5 scale."""
    return SCHMID_CMAP(SCHMID_NORM(m))


def schmid_mappable() -> ScalarMappable:
    return ScalarMappable(norm=SCHMID_NORM, cmap=SCHMID_CMAP)


@dataclass
class Selection:
    """Selected glide plane and glide direction (canonical index keys) or None."""

    plane: tuple | None = None
    direction: tuple | None = None
