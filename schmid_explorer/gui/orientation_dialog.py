# SPDX-License-Identifier: GPL-3.0-or-later
"""Dialog with the orientation map: a click sets the loading axis."""

from __future__ import annotations

import numpy as np

from ..core import orientation_map, stereo
from ..core.schmid import DIRECTION, Analysis
from .figure_panel import MapPanel
from .qt import QtWidgets, Signal
from .text import pretty


class OrientationDialog(QtWidgets.QDialog):
    """Non-modal: the main window follows every click, so orientations can be explored."""

    axisPicked = Signal(object)            # three Miller indices

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pick the loading axis on the orientation map")
        self._analysis = None
        self._values = None

        self.panel = MapPanel()
        self.panel.clicked.connect(self._clicked)
        self.panel.hovered.connect(self._hovered)
        self.max_index = QtWidgets.QSpinBox()
        self.max_index.setRange(1, 12)
        self.max_index.setValue(5)
        self.max_index.setToolTip("A clicked position is replaced by the nearest crystal direction\n"
                                  "whose indices do not exceed this value.")
        self.readout = QtWidgets.QLabel("Move the mouse over the map; click to set the loading axis.")
        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(self.close)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Largest index"))
        row.addWidget(self.max_index)
        row.addWidget(self.readout, 1)
        row.addWidget(close)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.panel, 1)
        layout.addLayout(row)
        self.resize(640, 700)

    def show_analysis(self, analysis: Analysis):
        self._analysis = analysis
        _, _, self._values = orientation_map.schmid_map(analysis, pixels=121)
        self.panel.show_analysis(analysis)

    def _snap(self, x: float, y: float) -> tuple:
        lattice = self._analysis.lattice
        vector = stereo.inverse_project(np.array([x, y])) @ orientation_map.standard_frame(lattice)
        return orientation_map.snap_to_indices(lattice, vector, self._analysis.loading.kind,
                                               self.max_index.value())

    def _axis_text(self, indices) -> str:
        lattice = self._analysis.lattice
        if self._analysis.loading.kind == DIRECTION:
            return pretty(lattice.direction_text(indices))
        return "⟂ " + pretty(lattice.plane_text(indices))

    def _clicked(self, x: float, y: float):
        if self._analysis is not None:
            self.axisPicked.emit(self._snap(x, y))

    def _hovered(self, position):
        if position is None or self._analysis is None:
            self.readout.setText("Move the mouse over the map; click to set the loading axis.")
            return
        x, y = position
        pixels = self._values.shape[0]
        column = int(round((x + 1.0) / 2.0 * (pixels - 1)))
        row = int(round((y + 1.0) / 2.0 * (pixels - 1)))
        value = self._values[row, column]
        quantity = "lowest σ_y" if self._analysis.use_crss else "highest m"
        text = f"near {self._axis_text(self._snap(x, y))}"
        if np.isfinite(value):
            text += f":  {quantity} ≈ {value:.3f}"
        self.readout.setText(text)
