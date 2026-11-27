# SPDX-License-Identifier: GPL-3.0-or-later
"""The figures can be drawn for every slip system (no display needed)."""

import numpy as np
import pytest
from matplotlib.figure import Figure

from schmid_explorer.core import inverse_pole_figure, stereo
from schmid_explorer.core.schmid import (
    COMPRESSION, DIRECTION, PLANE_NORMAL, TENSION, Loading, analyse, force_sign,
)
from schmid_explorer.core.slip_systems import STRUCTURES
from schmid_explorer.plotting.ipf_plot import draw_ipf
from schmid_explorer.plotting.map_plot import draw_orientation_map
from schmid_explorer.plotting.pillar_plot import PillarOptions, draw_pillar, suggested_view
from schmid_explorer.plotting.stereo_plot import StereoOptions, draw_stereo
from schmid_explorer.plotting.style import Selection

CASES = [
    ("fcc", (0, 1, 2), 1.0),
    ("bcc", (0, 0, 1), 1.0),
    ("bcc", (1, 4, 9), 1.0),
    ("hcp", (0, 0, 1), 1.624),      # steep pyramidal planes leave the pillar through its top face
    ("hcp", (1, 0, 1), 1.856),
]


@pytest.mark.parametrize("structure, axis, c_over_a", CASES)
def test_pillar_and_projection_for_every_system(structure, axis, c_over_a):
    families = [family.key for family in STRUCTURES[structure].families]
    for sense in (TENSION, COMPRESSION):
        analysis = analyse(structure, Loading(axis, sense=sense), family_keys=families, c_over_a=c_over_a)
        rotation, _ = stereo.sample_frame(analysis.lattice, analysis.axis, sign=force_sign(sense))
        fig = Figure()
        for result in analysis.results:
            plane = Selection(plane=result.plane_key)
            system = Selection(plane=result.plane_key, direction=result.direction_key)
            for selection, slip in ((plane, 0.0), (system, 0.0), (system, 0.9)):
                view = suggested_view(analysis, rotation, selection)
                draw_pillar(fig, analysis, rotation, selection, PillarOptions(slip_amount=slip, view=view))
                fig.canvas.draw()
        options = StereoOptions(traces=True, reference_poles=True, wulff_net=True, circle_45=True)
        draw_stereo(fig, analysis, rotation, Selection(plane=analysis.results[0].plane_key,
                                                       direction=analysis.results[0].direction_key), options)
        fig.canvas.draw()


@pytest.mark.parametrize("structure, axis, c_over_a", CASES)
def test_suggested_view_depends_on_the_plane_only(structure, axis, c_over_a):
    families = [family.key for family in STRUCTURES[structure].families]
    views = {}
    for sense in (TENSION, COMPRESSION):
        analysis = analyse(structure, Loading(axis, sense=sense), family_keys=families, c_over_a=c_over_a)
        rotation, _ = stereo.sample_frame(analysis.lattice, analysis.axis, sign=force_sign(sense))
        for result in analysis.results:
            plane = suggested_view(analysis, rotation, Selection(plane=result.plane_key))
            system = suggested_view(analysis, rotation, Selection(result.plane_key, result.direction_key))
            assert system == plane                             # the direction does not turn the pillar
            assert np.allclose(views.setdefault(result.plane_key, plane), plane)    # nor does the sense


def test_orientation_map_draws():
    fig = Figure()
    draw_orientation_map(fig, analyse("fcc", Loading((1, 2, 3))), pixels=61)
    fig.canvas.draw()


@pytest.mark.parametrize("structure, indices, kind, c_over_a, texts", [
    ("fcc", (0, 1, 2), DIRECTION, 1.0, ["loading axis $[012]$"]),
    ("fcc", (1, 2, 3), DIRECTION, 1.0, ["loading axis $[123]$", r"equivalent to $[\bar{1}23]$"]),
    ("hcp", (0, 1, 2), PLANE_NORMAL, 1.624, [r"$(01\bar{1}2)$", r"equivalent to $\perp$$(10\bar{1}2)$"]),
])
def test_inverse_pole_figure_marks_the_loading_axis(structure, indices, kind, c_over_a, texts):
    fig = Figure(figsize=(3.2, 1.5))
    for sense in (TENSION, COMPRESSION):
        analysis = analyse(structure, Loading(indices, kind, sense), c_over_a=c_over_a)
        ax = draw_ipf(fig, analysis)
        fig.canvas.draw()
        marker = ax.collections[-1].get_offsets()[0]
        assert np.allclose(marker, inverse_pole_figure.triangle_point(analysis.lattice, analysis.axis))
        outline = ax.patches[0].get_xy()                      # the star lies inside the triangle
        assert outline[:, 0].min() - 1e-9 <= marker[0] <= outline[:, 0].max() + 1e-9
        assert outline[:, 1].min() - 1e-9 <= marker[1] <= outline[:, 1].max() + 1e-9
        title = fig.texts[0].get_text()
        assert all(text in title for text in texts)
        assert ("equivalent" in title) == (len(texts) > 1)
        assert len(ax.texts) == 3                             # the three corner labels
