# SPDX-License-Identifier: GPL-3.0-or-later
"""Typeset an equation with matplotlib's mathtext (no LaTeX needed); used by the help window."""

from __future__ import annotations

import io

from matplotlib.figure import Figure


def equation_png(tex: str, fontsize: float = 11.0, dpi: int = 192) -> bytes:
    """PNG image (transparent background) of the mathtext expression `tex`, without the $ signs."""
    tex = tex.replace(r"\frac", r"\dfrac")                 # full-size fractions
    fig = Figure(figsize=(0.1, 0.1))
    fig.text(0, 0, f"${tex}$", fontsize=fontsize, math_fontfamily="cm")
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0.03, transparent=True)
    return buffer.getvalue()


def figure_png(fig: Figure, dpi: float = 192) -> bytes:
    """PNG image of a matplotlib figure."""
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi)
    return buffer.getvalue()
