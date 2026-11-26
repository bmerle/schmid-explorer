# SPDX-License-Identifier: GPL-3.0-or-later
"""Figures of the documentation.

Everything that also appears in the program (projection, pillar sketch, inverse pole
figure, orientation map) is drawn by `schmid_explorer.plotting`, i.e. by the same code as in the GUI, and the
screenshots are taken from the running program. Only the explanatory sketches (unit
cells with their slip systems, principle of the stereographic projection) are drawn here.
"""

from __future__ import annotations

from itertools import combinations, product
from pathlib import Path

import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

from schmid_explorer.core import stereo
from schmid_explorer.core.lattice import CUBIC, HEXAGONAL, Lattice, mb_direction_to_miller
from schmid_explorer.core.schmid import COMPRESSION, Loading, analyse, force_sign
from schmid_explorer.core.slip_systems import HCP_C_OVER_A, STRUCTURES
from schmid_explorer.plotting.ipf_plot import draw_ipf
from schmid_explorer.plotting.map_plot import draw_orientation_map
from schmid_explorer.plotting.pillar_plot import PillarOptions, arrow_3d, draw_pillar, suggested_view
from schmid_explorer.plotting.stereo_plot import StereoOptions, draw_stereo
from schmid_explorer.plotting.style import (
    ANGLE_COLOUR, BURGERS_COLOUR, LOAD_COLOUR, NORMAL_COLOUR, Selection, schmid_colour,
)

DPI = 220
C_OVER_A_MG = HCP_C_OVER_A["Mg"]
CRSS_EXAMPLE = {"hcp_basal_a": 1.0, "hcp_prism_a": 40.0, "hcp_pyr1_a": 50.0,
                "hcp_pyr1_ca": 80.0, "hcp_pyr2_ca": 80.0}     # illustration only, see the text
CA_COLOUR = "#c8541a"                                         # <c+a> directions in the hcp sketches
PLANE_FACE = (0.99, 0.86, 0.35, 0.55)


def build_all(folder: Path, screenshots: bool = True) -> dict:
    """Create all figures in `folder`; returns {name: path}."""
    folder.mkdir(parents=True, exist_ok=True)
    figures = {}

    def save(name, fig):
        path = folder / f"{name}.png"
        fig.savefig(path, dpi=DPI)
        figures[name] = path

    # ---- explanatory sketches
    save("cells_cubic", cubic_cells())
    save("cells_hcp", hcp_cells())
    save("stereo_principle", stereo_principle())

    # ---- figures of the program
    fcc012 = analyse("fcc", Loading((0, 1, 2)))                       # tension, as at program start
    best = _system(fcc012, 0)                                         # the keys do not depend on the sense
    save("fcc012_stereo", stereo_figure(fcc012))
    save("fcc012_stereo_plane", stereo_figure(fcc012, Selection(plane=best.plane)))
    save("fcc012_stereo_system", stereo_figure(fcc012, best, StereoOptions(circle_45=True)))
    save("fcc012_pillar", pillar_figure(fcc012, best))
    save("fcc012_pillar_plain", pillar_figure(fcc012))
    save("fcc012_slip", pillar_figure(fcc012, best, slip=0.6))
    fcc012_compression = analyse("fcc", Loading((0, 1, 2), sense=COMPRESSION))
    save("fcc012_pillar_compression", pillar_figure(fcc012_compression, best))
    save("fcc012_slip_compression", pillar_figure(fcc012_compression, best, slip=0.6))
    save("fcc012_stereo_system_compression",
         stereo_figure(fcc012_compression, best, StereoOptions(circle_45=True)))
    save("fcc_map", map_figure(fcc012))

    fcc001 = analyse("fcc", Loading((0, 0, 1)))
    save("fcc001_stereo", stereo_figure(fcc001, options=StereoOptions(traces=True, circle_45=True)))
    fcc123 = analyse("fcc", Loading((1, 2, 3)))
    save("fcc123_stereo", stereo_figure(fcc123, _system(fcc123, 0), StereoOptions(circle_45=True)))
    save("fcc123_ipf", ipf_figure(fcc123))

    bcc012 = analyse("bcc", Loading((0, 1, 2)))
    save("bcc012_stereo", stereo_figure(bcc012, _system(bcc012, 0)))
    bcc_all = analyse("bcc", Loading((0, 0, 1)), family_keys=[f.key for f in STRUCTURES["bcc"].families])
    save("bcc001_all_stereo", stereo_figure(bcc_all, _system(bcc_all, 0)))
    save("bcc_all_map", map_figure(bcc_all))

    mg_c = analyse("hcp", Loading((0, 0, 1)), c_over_a=C_OVER_A_MG)
    save("mg_c_stereo", stereo_figure(mg_c, _system(mg_c, 0)))
    save("mg_c_pillar", pillar_figure(mg_c, _system(mg_c, 0)))
    axis = mb_direction_to_miller((2, -1, -1, 3))
    mg_schmid = analyse("hcp", Loading(axis), c_over_a=C_OVER_A_MG)
    mg_crss = analyse("hcp", Loading(axis), c_over_a=C_OVER_A_MG, crss=CRSS_EXAMPLE, use_crss=True)
    save("mg_2113_stereo", stereo_figure(mg_schmid, _system(mg_schmid, 0)))
    save("mg_2113_ipf", ipf_figure(mg_schmid))
    save("mg_2113_pillar_crss", pillar_figure(mg_crss, _system(mg_crss, 0), slip=0.5))
    save("mg_map", map_figure(mg_schmid))
    save("mg_map_crss", map_figure(mg_crss))

    if screenshots:
        figures.update(gui_screenshots(folder))
    return figures


# --------------------------------------------------------------------------- program figures
def _system(analysis, index: int) -> Selection:
    result = analysis.results[index]
    return Selection(plane=result.plane_key, direction=result.direction_key)


def _frame(analysis) -> np.ndarray:
    """Sample frame of the analysis: z along the force on the top face."""
    return stereo.sample_frame(analysis.lattice, analysis.axis, sign=force_sign(analysis.loading.sense))[0]


def stereo_figure(analysis, selection: Selection = None, options: StereoOptions = None) -> Figure:
    fig = Figure(figsize=(4.7, 4.7))
    rotation = _frame(analysis)
    draw_stereo(fig, analysis, rotation, selection or Selection(), options or StereoOptions())
    return fig


def pillar_figure(analysis, selection: Selection = None, slip: float = 0.0) -> Figure:
    fig = Figure(figsize=(4.2, 4.7))
    rotation = _frame(analysis)
    selection = selection or Selection()
    view = suggested_view(analysis, rotation, selection)
    draw_pillar(fig, analysis, rotation, selection, PillarOptions(slip_amount=slip, view=view))
    return fig


def map_figure(analysis) -> Figure:
    fig = Figure(figsize=(4.7, 4.7))
    draw_orientation_map(fig, analysis)
    return fig


def ipf_figure(analysis) -> Figure:
    fig = Figure(figsize=(3.2, 1.5))                   # the shape of the small panel in the program
    draw_ipf(fig, analysis)
    return fig


# --------------------------------------------------------------------------- unit cells
def _axes_3d(fig, position, elev, azim, limits):
    ax = fig.add_axes(position, projection="3d", computed_zorder=False)
    ax.set_proj_type("ortho")
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.patch.set_visible(False)                        # neighbouring sketches may overlap a little
    (x0, x1), (y0, y1), (z0, z1) = limits
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_zlim(z0, z1)
    ax.set_box_aspect((x1 - x0, y1 - y0, z1 - z0), zoom=1.25)
    return ax


LABEL_BOX = dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.75)


def _atoms(ax, points, size=26):
    points = np.asarray(points, dtype=float)
    ax.scatter(points[:, 0], points[:, 1], points[:, 2], s=size, color="#8d96a3", edgecolors="#4c535d",
               linewidths=0.5, depthshade=False, zorder=3)


def _plane(ax, polygon):
    ax.add_collection3d(Poly3DCollection([polygon], facecolors=[PLANE_FACE], edgecolors="#b58900",
                                         linewidths=1.0, zorder=2))


def _plane_in_cube(hkl, constant: float) -> np.ndarray:
    """Polygon cut out of the unit cube by the plane h x + k y + l z = constant."""
    hkl = np.asarray(hkl, dtype=float)
    corners = [np.array(c, dtype=float) for c in product((0, 1), repeat=3)]
    points = []
    for a, b in combinations(corners, 2):
        if not np.isclose(np.abs(a - b).sum(), 1.0):
            continue                                   # not an edge of the cube
        fa, fb = hkl @ a - constant, hkl @ b - constant
        if abs(fa) < 1e-12:
            points.append(a)
        if abs(fb) < 1e-12:
            points.append(b)
        if fa * fb < -1e-12:
            points.append(a + (b - a) * fa / (fa - fb))
    points = np.unique(np.round(points, 9), axis=0)
    centre = points.mean(axis=0)
    normal = hkl / np.linalg.norm(hkl)
    u = points[0] - centre
    u = u / np.linalg.norm(u)
    v = np.cross(normal, u)
    order = np.argsort(np.arctan2((points - centre) @ v, (points - centre) @ u))
    return points[order]


def cubic_cells() -> Figure:
    """fcc and bcc unit cells with one plane of every slip family and its slip directions."""
    lattice = Lattice(CUBIC)
    corners = np.array(list(product((0, 1), repeat=3)), dtype=float)
    edges = [(a, b) for a, b in combinations(corners, 2) if np.isclose(np.abs(a - b).sum(), 1.0)]
    faces = np.array([c for c in product((0, 0.5, 1), repeat=3)
                      if sorted(c) in ([0, 0.5, 0.5], [0.5, 0.5, 1])], dtype=float)
    centre = np.array([[0.5, 0.5, 0.5]])
    diagonal = (np.array([1.0, 0, 0]), (-1, 1, 1), 0.5)                  # start point, [uvw], label position
    panels = [
        ("fcc", STRUCTURES["fcc"].family("fcc_111_110"), (1, 1, 1), 1, np.vstack([corners, faces]),
         [(np.array([1.0, 0, 0]), (-1, 1, 0), 0.5), (np.array([0, 1.0, 0]), (0, -1, 1), 0.5),
          (np.array([0, 0, 1.0]), (1, 0, -1), 0.5)]),
        ("bcc", STRUCTURES["bcc"].family("bcc_110_111"), (1, 1, 0), 1, np.vstack([corners, centre]),
         [(np.array([1.0, 0, 0]), (-1, 1, 1), 0.80), (np.array([0, 1.0, 0]), (1, -1, 1), 0.80)]),
        ("bcc", STRUCTURES["bcc"].family("bcc_112_111"), (2, 1, 1), 2, np.vstack([corners, centre]),
         [diagonal]),
        ("bcc", STRUCTURES["bcc"].family("bcc_123_111"), (3, 1, 2), 3, np.vstack([corners, centre]),
         [diagonal]),
    ]
    fig = Figure(figsize=(7.4, 2.6))
    for column, (structure, family, hkl, constant, atoms, directions) in enumerate(panels):
        left = 0.244 * column
        ax = _axes_3d(fig, [left, 0.0, 0.244, 0.80], 17, 24, [(-0.05, 1.05)] * 3)
        ax.add_collection3d(Line3DCollection(edges, colors="#4c535d", linewidths=0.8, zorder=1))
        _plane(ax, _plane_in_cube(hkl, constant))
        _atoms(ax, atoms)
        for start, uvw, fraction in directions:
            assert np.dot(hkl, uvw) == 0                               # direction lies in the plane
            arrow_3d(ax, start, np.asarray(uvw, dtype=float), BURGERS_COLOUR, lw=1.6)
            tip = start + fraction * np.asarray(uvw) + 0.06 * lattice.plane_normal(hkl)
            ax.text(*tip, lattice.direction_tex(uvw), color=BURGERS_COLOUR, fontsize=7, ha="center",
                    va="bottom", zorder=10, bbox=LABEL_BOX)
        for name, position in (("x", (1.16, 0, 0)), ("y", (-0.06, 1.05, -0.11)), ("z", (0, 0, 1.12))):
            ax.text(*position, name, fontsize=7, style="italic", color="#5d646f", ha="center", va="center")
        fig.text(left + 0.122, 0.925, f"{structure}:  {family.label_tex}", ha="center", va="baseline", fontsize=9)
        fig.text(left + 0.122, 0.845, f"plane {lattice.plane_tex(hkl)}", ha="center", va="baseline",
                 fontsize=8, color="#8a6a00")
    return fig


def hcp_cells() -> Figure:
    """Hexagonal prism with one plane of every hcp slip family and its slip directions."""
    lattice = Lattice(HEXAGONAL, 1.633)
    c = lattice.c_over_a
    ring = [np.array([np.cos(np.radians(60 * k)), np.sin(np.radians(60 * k)), 0.0]) for k in range(6)]
    up = np.array([0.0, 0.0, c])
    edges = []
    for k in range(6):
        edges += [(ring[k], ring[(k + 1) % 6]), (ring[k] + up, ring[(k + 1) % 6] + up), (ring[k], ring[k] + up)]
    middle = [lattice.direct @ np.array(p) for p in ((2 / 3, 1 / 3, 0.5), (-1 / 3, 1 / 3, 0.5), (-1 / 3, -2 / 3, 0.5))]
    atoms = np.array(ring + [r + up for r in ring] + [np.zeros(3), up] + middle)
    v = ring                                                       # corners of the bottom hexagon
    structure = STRUCTURES["hcp"]
    # family, second family, (hkl), polygon, arrows: (start, [uvw], colour, label position along the arrow)
    panels = [
        ("hcp_basal_a", None, (0, 0, 1), [r + up for r in ring],
         [(up, (1, 0, 0), BURGERS_COLOUR, 1.75), (up, (0, 1, 0), BURGERS_COLOUR, 1.3),
          (up, (-1, -1, 0), BURGERS_COLOUR, 1.3)]),
        ("hcp_prism_a", None, (1, 0, 0), [v[0], v[1], v[1] + up, v[0] + up],
         [(v[0], (0, 1, 0), BURGERS_COLOUR, 0.5)]),
        ("hcp_pyr1_a", "hcp_pyr1_ca", (1, 0, 1), [v[0], v[1], v[2] + up, v[5] + up],
         [(v[0], (0, 1, 0), BURGERS_COLOUR, 0.5), (v[0], (-1, 0, 1), CA_COLOUR, 0.45),
          (v[1], (-1, -1, 1), CA_COLOUR, 0.45)]),
        ("hcp_pyr2_ca", None, (1, 1, 2), [v[0], v[2], v[3] + up, v[5] + up],
         [(v[0], (-1, -1, 1), CA_COLOUR, 0.5)]),
    ]
    fig = Figure(figsize=(7.4, 2.85))
    for column, (key, second, hkl, polygon, arrows) in enumerate(panels):
        polygon = np.array(polygon)
        normal = lattice.plane_normal(hkl)
        assert np.allclose((polygon - polygon[0]) @ normal, 0.0)       # the sketch shows the right plane
        ax = _axes_3d(fig, [0.25 * column, 0.065, 0.25, 0.76], 16, 14, [(-1.05, 1.05), (-1.05, 1.05), (-0.05, c + 0.05)])
        ax.add_collection3d(Line3DCollection(edges, colors="#4c535d", linewidths=0.8, zorder=1))
        _plane(ax, polygon)
        _atoms(ax, atoms, size=16)
        middle_of_plane = polygon.mean(axis=0)
        for start, uvw, colour, fraction in arrows:
            vector = lattice.direct @ np.asarray(uvw, dtype=float)
            assert np.dot(hkl, uvw) == 0
            arrow_3d(ax, start, vector, colour, lw=1.6)
            # label beside the arrow, within the plane, on the side away from the middle of the plane
            # (a position > 1 puts it beyond the tip instead)
            position = start + fraction * vector
            if fraction < 1.0:
                sideways = np.cross(normal, vector)
                sideways = sideways / np.linalg.norm(sideways)
                position = position + 0.26 * sideways * np.sign(sideways @ (position - middle_of_plane) or 1.0)
            ax.text(*(position + 0.05 * normal), lattice.direction_tex(uvw), color=colour,
                    fontsize=6.5, ha="center", va="center", zorder=10, bbox=LABEL_BOX)
        family = structure.family(key)
        title = family.name.replace("<a>", r"$\langle a\rangle$").replace("<c+a>", r"$\langle c{+}a\rangle$")
        if second:
            title = title + " and " + r"$\langle c{+}a\rangle$"
        fig.text(0.25 * column + 0.125, 0.93, title, ha="center", va="baseline", fontsize=9)
        fig.text(0.25 * column + 0.125, 0.855, f"plane {lattice.plane_tex(hkl)}", ha="center", va="baseline",
                 fontsize=8, color="#8a6a00")
    fig.text(0.5, 0.015, r"blue: $\langle a\rangle$ directions $\frac{1}{3}\langle 11\bar{2}0\rangle$"
             r"       orange: $\langle c{+}a\rangle$ directions $\frac{1}{3}\langle 11\bar{2}3\rangle$",
             ha="center", va="bottom", fontsize=8, color="#3d434c")
    return fig


# --------------------------------------------------------------------------- projection principle
def stereo_principle() -> Figure:
    """Construction of the stereographic projection (section) and the resulting plot (seen against the force)."""
    theta = np.radians(50.0)                                          # P: plane normal, angle to the force
    lam = np.radians(40.0)                                            # Q: slip direction, angle to the force
    point = np.array([np.sin(theta), np.cos(theta)])                  # P in the section plane
    other = np.array([-np.sin(lam), np.cos(lam)])                     # Q in the section plane
    radius = np.tan(theta / 2.0)                                      # distance of P' from the centre
    radius_other = np.tan(lam / 2.0)                                  # distance of Q' from the centre
    assert np.isclose(point @ other, 0.0)                             # Q lies in the plane with the normal P
    assert np.isclose(stereo.project(np.array([point[0], 0.0, point[1]]))[0], radius)
    assert np.isclose(stereo.project(np.array([other[0], 0.0, other[1]]))[0], -radius_other)
    t = np.linspace(0, 2 * np.pi, 361)
    fig = Figure(figsize=(7.4, 3.45))

    ax = fig.add_axes([0.0, 0.02, 0.56, 0.90])
    ax.set_aspect("equal")
    ax.axis("off")
    ax.plot(np.cos(t), np.sin(t), color="black", lw=1.2)
    ax.plot([-1.5, 1.95], [0, 0], color="black", lw=1.0)
    ax.plot([0, 0], [-1.0, 1.0], color=LOAD_COLOUR, lw=0.9, ls=(0, (7, 3, 1.5, 3)))
    ax.annotate("", xy=(0, 1.42), xytext=(0, 1.0), arrowprops=dict(arrowstyle="-|>", color=LOAD_COLOUR, lw=1.8,
                                                                   shrinkA=0, shrinkB=0))
    for tip, colour in ((point, NORMAL_COLOUR), (other, BURGERS_COLOUR)):
        ax.plot([0, tip[0]], [-1, tip[1]], color="#5d646f", lw=1.0, ls="--")       # projection from S
        ax.annotate("", xy=tip, xytext=(0, 0), arrowprops=dict(arrowstyle="-|>", color=colour, lw=1.6,
                                                               shrinkA=0, shrinkB=0))
        ax.plot(*tip, "o", color=colour, ms=5)
    ax.plot(radius, 0, "o", color=schmid_colour(0.49), mec="black", ms=7)
    ax.plot(-radius_other, 0, "s", color=schmid_colour(0.49), mec="black", ms=6.5)
    ax.plot(0, -1, "o", color="black", ms=4)
    for start, stop, centre, size in ((np.pi / 2 - theta, np.pi / 2, 0.0, 0.33),             # theta, lambda at O
                                      (np.pi / 2, np.pi / 2 + lam, 0.0, 0.33),
                                      (np.pi / 2 - theta / 2, np.pi / 2, -1.0, 0.42),        # half angles at S
                                      (np.pi / 2, np.pi / 2 + lam / 2, -1.0, 0.42)):
        arc = np.linspace(start, stop, 40)
        ax.plot(size * np.cos(arc), centre + size * np.sin(arc), color=ANGLE_COLOUR, lw=1.3)
    ax.annotate("", xy=(radius, -0.13), xytext=(0, -0.13),
                arrowprops=dict(arrowstyle="<->", color="black", lw=0.8, shrinkA=0, shrinkB=0))
    labels = [
        (0.08, 1.33, r"force $F \parallel z$", LOAD_COLOUR, "left"),
        (point[0] + 0.07, point[1] + 0.07, "$P$ (plane\n" r"normal $\mathbf{n}$)", NORMAL_COLOUR, "left"),
        (other[0] - 0.07, other[1] + 0.07, "$Q$ (slip\n" r"direction $\mathbf{b}$)", BURGERS_COLOUR, "right"),
        (0.11, 0.42, r"$\theta$", ANGLE_COLOUR, "left"), (0.07, -0.47, r"$\theta/2$", ANGLE_COLOUR, "left"),
        (-0.09, 0.43, r"$\lambda$", ANGLE_COLOUR, "right"), (-0.19, -0.64, r"$\lambda/2$", ANGLE_COLOUR, "right"),
        (radius + 0.13, 0.10, "$P'$", "black", "left"), (-radius_other - 0.08, -0.12, "$Q'$", "black", "right"),
        (radius + 0.10, -0.14, r"$r=\tan(\theta/2)$", "black", "left"),
        (0.08, -1.07, "$S$", "black", "left"), (-0.06, -0.10, "$O$", "black", "right"),
        (1.08, 0.09, "projection plane", "black", "left"), (0.80, -0.80, "unit sphere", "black", "left"),
    ]
    for x, y, text, colour, ha in labels:
        ax.text(x, y, text, color=colour, fontsize=8.5, ha=ha, va="center")
    ax.set_xlim(-1.75, 2.0)
    ax.set_ylim(-1.2, 1.5)
    ax.set_title("section through the sphere", fontsize=9, pad=2)

    ax = fig.add_axes([0.60, 0.30, 0.38, 0.62])
    ax.set_aspect("equal")
    ax.axis("off")
    ax.plot(np.cos(t), np.sin(t), color="black", lw=1.0)
    pole = np.array([np.sin(theta), 0.0, np.cos(theta)])
    trace = stereo.great_circle(pole)
    ax.plot(trace[:, 0], trace[:, 1], color=NORMAL_COLOUR, lw=1.8)
    ax.plot([-radius_other, radius], [0, 0], color=ANGLE_COLOUR, lw=1.1)
    ax.plot(0, 0, "o", color="white", mec="black", mew=1.2, ms=9)
    ax.plot(0, 0, "o", color="black", ms=3.2)
    ax.plot(radius, 0, "o", color=schmid_colour(0.49), mec="black", ms=7)
    ax.plot(-radius_other, 0, "s", color=schmid_colour(0.49), mec="black", ms=6.5)
    ax.text(radius + 0.07, 0.10, "$P'$", color="black", fontsize=8.5, ha="left", va="center")
    ax.text(-radius_other - 0.07, 0.10, "$Q'$", color="black", fontsize=8.5, ha="right", va="center")
    ax.text(radius / 2 + 0.06, -0.11, r"$\tan(\theta/2)$", color=ANGLE_COLOUR, fontsize=8.5, ha="center",
            va="center")
    ax.set_xlim(-1.06, 1.06)
    ax.set_ylim(-1.06, 1.06)
    ax.set_title("projection: the force points towards the viewer", fontsize=9, pad=2)
    entries = [
        ((Line2D([], [], marker="o", ls="", markerfacecolor="none", markeredgecolor="black",
                 markeredgewidth=1.2, markersize=8),
          Line2D([], [], marker="o", ls="", color="black", markersize=3)), r"force $F \parallel z$"),
        (Line2D([], [], marker="o", ls="", markerfacecolor=schmid_colour(0.49), markeredgecolor="black",
                markersize=6.5), r"$P'$: pole of the plane, $r=\tan(\theta/2)$"),
        (Line2D([], [], marker="s", ls="", markerfacecolor=schmid_colour(0.49), markeredgecolor="black",
                markersize=6), r"$Q'$: slip direction, $r=\tan(\lambda/2)$"),
        (Line2D([], [], color=NORMAL_COLOUR, lw=1.8), "trace of the plane with the normal $P$"),
        (Line2D([], [], color="black", lw=1.0), "primitive circle (90° from the force)"),
    ]
    fig.legend(handles=[handle for handle, _text in entries], labels=[text for _handle, text in entries],
               loc="lower center", bbox_to_anchor=(0.79, 0.0), fontsize=7.5, frameon=False,
               handlelength=1.6, labelspacing=0.3)
    return fig


# --------------------------------------------------------------------------- screenshots
def gui_screenshots(folder: Path) -> dict:
    """Screenshots of the running program (the windows appear briefly on the screen)."""
    from schmid_explorer.gui.main_window import MainWindow
    from schmid_explorer.gui.qt import QtCore, QtGui, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow()
    window.resize(1320, 880)
    window.show()
    app.processEvents()
    figures = {}

    def grab(name, widget, callouts=()):
        for _ in range(4):                             # the layout settles over several event rounds
            app.processEvents()
        pixmap = widget.grab()
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        font = painter.font()
        font.setBold(True)
        font.setPointSize(11)
        painter.setFont(font)
        for number, (target, fx, fy) in enumerate(callouts, start=1):
            corner = target.mapTo(widget, QtCore.QPoint(0, 0))
            centre = QtCore.QPoint(corner.x() + int(fx * target.width()), corner.y() + int(fy * target.height()))
            painter.setBrush(QtGui.QColor("#9b0a45"))
            painter.setPen(QtGui.QPen(QtGui.QColor("white"), 2))
            painter.drawEllipse(centre, 13, 13)
            painter.drawText(QtCore.QRect(centre.x() - 13, centre.y() - 13, 26, 26),
                             int(QtCore.Qt.AlignmentFlag.AlignCenter), str(number))
        painter.end()
        path = folder / f"{name}.png"
        pixmap.save(str(path))
        figures[name] = path

    window.select(_system(window.analysis, 0))
    grab("gui_main_plain", window)
    grab("gui_main", window, [(window.settings, 0.93, 0.025), (window.pillar, 0.55, 0.03),
                              (window.stereo, 0.60, 0.03), (window.summary, 0.80, 0.5),
                              (window.table, 0.955, 0.55)])

    settings = window.settings
    settings.set_structure("hcp")
    settings.material.setCurrentIndex(settings.material.findText("Mg", QtCore.Qt.MatchFlag.MatchContains))
    settings.set_axis((1, 0, 1))                      # [2 -1 -1 3] in four indices
    settings.use_crss.setChecked(True)
    for key, value in CRSS_EXAMPLE.items():
        settings.set_family(key, True, crss=value)
    window.select(_system(window.analysis, 0))
    window.pillar.slip_slider.setValue(55)
    window.resize(1500, 940)                          # start-up size: room for the two CRSS columns
    grab("gui_hcp", window)

    settings.use_crss.setChecked(False)               # the map shows the Schmid factor again
    settings.set_structure("fcc")
    window.show_map()
    grab("gui_map", window.map_dialog)
    window.map_dialog.close()
    window.close()
    app.processEvents()
    return figures
