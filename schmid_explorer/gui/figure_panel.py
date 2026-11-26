# SPDX-License-Identifier: GPL-3.0-or-later
"""Matplotlib canvases with 'Copy' and 'Save as...' and the view-specific mouse handling."""

from __future__ import annotations

import io
import os

from ..core.schmid import Analysis
from ..plotting.ipf_plot import draw_ipf
from ..plotting.map_plot import draw_orientation_map
from ..plotting.pillar_plot import DEFAULT_VIEW, PillarOptions, draw_pillar, suggested_view
from ..plotting.stereo_plot import StereoOptions, StereoScene, draw_stereo
from ..plotting.style import Selection
from .qt import Figure, FigureCanvas, Qt, QtCore, QtGui, QtWidgets, Signal
from .text import pretty

EXPORT_DPI = 300
IMAGE_FILTERS = "PNG image (*.png);;SVG vector graphic (*.svg);;PDF document (*.pdf)"
MAX_SLIP = 0.9          # largest slip step of the slider, in pillar radii


class FigurePanel(QtWidgets.QWidget):
    """A titled matplotlib canvas with clipboard and file export."""

    message = Signal(str)

    def __init__(self, title: str, file_stem: str, parent=None):
        super().__init__(parent)
        self.file_stem = file_stem
        self.figure = Figure(figsize=(5.2, 5.2), dpi=100, facecolor="white")
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumSize(300, 300)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding,
                                  QtWidgets.QSizePolicy.Policy.Expanding)

        heading = QtWidgets.QLabel(title)
        font = heading.font()
        font.setBold(True)
        heading.setFont(font)
        self.copy_button = QtWidgets.QPushButton("Copy image")
        self.copy_button.setToolTip(f"Copy this figure to the clipboard ({EXPORT_DPI} dpi)")
        self.copy_button.clicked.connect(self.copy_image)
        self.save_button = QtWidgets.QPushButton("Save as…")
        self.save_button.setToolTip("Save this figure as PNG, SVG or PDF")
        self.save_button.clicked.connect(lambda: self.save_image())
        self._arrange(heading)

    def _arrange(self, heading):
        """Heading and export buttons above the canvas, view-specific controls below it."""
        self.header = QtWidgets.QHBoxLayout()
        self.header.addWidget(heading)
        self.header.addStretch(1)
        self.header.addWidget(self.copy_button)
        self.header.addWidget(self.save_button)
        self.footer = QtWidgets.QHBoxLayout()          # view-specific controls

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(self.header)
        layout.addWidget(self.canvas, 1)
        layout.addLayout(self.footer)

    # ---- export
    def image_bytes(self, fmt: str = "png") -> bytes:
        buffer = io.BytesIO()
        self.figure.savefig(buffer, format=fmt, dpi=EXPORT_DPI)
        return buffer.getvalue()

    def copy_image(self):
        image = QtGui.QImage.fromData(self.image_bytes("png"), "PNG")
        QtWidgets.QApplication.clipboard().setImage(image)
        self.message.emit("Image copied to the clipboard.")

    def save_image(self, path: str = None):
        if path is None:
            path, chosen = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save image", self.file_stem + ".png", IMAGE_FILTERS)
            if not path:
                return
            if not os.path.splitext(path)[1]:
                path += "." + chosen.split("*.")[1].rstrip(")")
        try:
            self.figure.savefig(path, dpi=EXPORT_DPI)
        except (OSError, ValueError) as error:
            QtWidgets.QMessageBox.warning(self, "Save image", f"Could not save the image:\n{error}")
            return
        self.message.emit(f"Image saved: {path}")


class StereoPanel(FigurePanel):
    """Stereographic projection; clicking a pole or a glide direction selects it."""

    planeClicked = Signal(object)
    directionClicked = Signal(object)
    backgroundClicked = Signal()

    def __init__(self, parent=None):
        super().__init__("Stereographic projection of the glide planes", "stereographic_projection",
                         parent)
        self.scene = StereoScene()
        self._analysis = None
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_move)
        hint = QtWidgets.QLabel("Click a pole (●) to select a glide plane, then one of its glide "
                                "directions (■). The centre is the force on the top face.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #5d646f;")
        self.footer.addWidget(hint, 1)

    def show_analysis(self, analysis: Analysis, rotation, selection: Selection,
                      options: StereoOptions):
        self._analysis = analysis
        self.scene = draw_stereo(self.figure, analysis, rotation, selection, options)
        self.canvas.draw_idle()

    def _hit(self, event):
        if event.xdata is None or not self.figure.axes or event.inaxes is not self.figure.axes[0]:
            return None
        return self.scene.hit(event.xdata, event.ydata)

    def _on_press(self, event):
        if event.button != 1:
            return
        hit = self._hit(event)
        if hit is None:
            self.backgroundClicked.emit()
        elif hit[0] == "plane":
            self.planeClicked.emit(hit[1])
        else:
            self.directionClicked.emit(hit[1])

    def _on_move(self, event):
        hit = self._hit(event)
        if hit is None or self._analysis is None:
            self.canvas.unsetCursor()
            QtWidgets.QToolTip.hideText()
            return
        self.canvas.setCursor(Qt.CursorShape.PointingHandCursor)
        QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), self._describe(*hit), self.canvas)

    def _describe(self, kind, key) -> str:
        analysis, lattice = self._analysis, self._analysis.lattice
        if kind == "plane":
            best = analysis.best_on_plane(key)
            return (f"Glide plane {pretty(lattice.plane_text(best.plane))}\n"
                    f"highest Schmid factor on this plane: m = {best.m:.4f}\n"
                    f"θ = {best.theta_deg:.1f}° between the force and its normal")
        for result in analysis.results:
            if result.direction_key == key:
                return (f"Slip direction {pretty(lattice.direction_text(result.direction))}\n"
                        "of the part of the pillar carrying the top face\n"
                        f"λ = {result.lambda_deg:.1f}° to the force")
        return ""


class PillarPanel(FigurePanel):
    """3-D sketch of the pillar; rotate with the mouse, shear it with the slider."""

    def __init__(self, parent=None):
        super().__init__("Pillar with the selected glide system", "pillar_sketch", parent)
        self.view = DEFAULT_VIEW
        self._axes = None
        self._state = None                 # (analysis, rotation, selection, labels)

        self.slip_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.slip_slider.setRange(0, 100)
        self.slip_slider.setToolTip("Let the selected slip system glide: the part of the pillar carrying\n"
                                    "the top face is displaced along the slip direction b.")
        self.slip_slider.valueChanged.connect(self.redraw)
        self.slip_label = QtWidgets.QLabel("Slip step")
        self.auto_view = QtWidgets.QCheckBox("Auto view")
        self.auto_view.setChecked(True)
        self.auto_view.setToolTip("Turn the pillar automatically so that the selected plane is well\n"
                                  "visible. The view is kept while you switch between the slip\n"
                                  "directions of this plane.")
        reset = QtWidgets.QPushButton("Reset view")
        reset.clicked.connect(self.reset_view)
        self.footer.addWidget(self.slip_label)
        self.footer.addWidget(self.slip_slider, 1)
        self.footer.addWidget(self.auto_view)
        self.footer.addWidget(reset)
        # after a mouse rotation: redraw (deferred) so that the labels follow the new view
        self.canvas.mpl_connect("button_release_event",
                                lambda event: QtCore.QTimer.singleShot(0, self.redraw))
        self._enable_slider(False)

    def show_analysis(self, analysis: Analysis, rotation, selection: Selection, labels: bool = True,
                      selection_changed: bool = False, plane_changed: bool = False):
        """`plane_changed`: another plane (or another crystal orientation) - only then Auto view turns
        the pillar; the view is kept while stepping through the slip directions of one plane."""
        self._remember_view()
        self._state = (analysis, rotation, selection, labels)
        if selection_changed:
            self.slip_slider.blockSignals(True)
            self.slip_slider.setValue(0)
            self.slip_slider.blockSignals(False)
        if plane_changed and self.auto_view.isChecked():
            self.view = suggested_view(analysis, rotation, selection)
        self._enable_slider(analysis.find(selection.plane, selection.direction) is not None)
        self._draw()

    def redraw(self, *_):
        if self._state is not None:
            self._remember_view()
            self._draw()

    def reset_view(self):
        if self._state is None:
            return
        analysis, rotation, selection, _ = self._state
        self.view = suggested_view(analysis, rotation, selection)
        self._axes = None
        self._draw()

    def _remember_view(self):
        if self._axes is not None:         # keep the orientation chosen with the mouse
            self.view = (float(self._axes.elev), float(self._axes.azim))

    def _enable_slider(self, enabled: bool):
        self.slip_slider.setEnabled(enabled)
        self.slip_label.setEnabled(enabled)

    def _draw(self):
        analysis, rotation, selection, labels = self._state
        options = PillarOptions(slip_amount=MAX_SLIP * self.slip_slider.value() / 100.0,
                                view=self.view, labels=labels)
        self._axes = draw_pillar(self.figure, analysis, rotation, selection, options)
        self.canvas.draw_idle()


class IpfPanel(FigurePanel):
    """Small inverse pole figure: the loading axis in the standard triangle."""

    HEIGHT = 150                           # of the canvas, in pixels

    def __init__(self, parent=None):
        super().__init__("Inverse\npole figure", "inverse_pole_figure", parent)
        self.canvas.setMinimumSize(220, self.HEIGHT)
        self.canvas.setFixedHeight(self.HEIGHT)
        self.canvas.setToolTip(
            "Inverse pole figure: the loading axis (★) in the frame of the crystal.\n"
            "The standard triangle contains every crystal direction once; all other\n"
            "directions are equivalent by symmetry to one inside the triangle.\n"
            "Tension and compression along the same axis give the same point.")

    def _arrange(self, heading):
        """Compact: heading and export buttons in a column beside the small canvas."""
        side = QtWidgets.QVBoxLayout()
        side.addWidget(heading)
        side.addWidget(self.copy_button)
        side.addWidget(self.save_button)
        side.addStretch(1)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(self.canvas, 1)
        layout.addLayout(side)

    def show_analysis(self, analysis: Analysis):
        draw_ipf(self.figure, analysis)
        self.canvas.draw_idle()


class MapPanel(FigurePanel):
    """Orientation map; a click reports the stereographic coordinates."""

    clicked = Signal(float, float)
    hovered = Signal(object)               # (x, y) or None

    def __init__(self, parent=None):
        super().__init__("Orientation map (standard projection of the crystal)", "orientation_map",
                         parent)
        self._axes = None
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_move)

    def show_analysis(self, analysis: Analysis):
        self._axes = draw_orientation_map(self.figure, analysis)
        self.canvas.draw_idle()

    def _inside(self, event) -> bool:
        return (event.inaxes is self._axes and event.xdata is not None
                and event.xdata ** 2 + event.ydata ** 2 <= 1.0)

    def _on_press(self, event):
        if event.button == 1 and self._inside(event):
            self.clicked.emit(float(event.xdata), float(event.ydata))

    def _on_move(self, event):
        if self._inside(event):
            self.canvas.setCursor(Qt.CursorShape.CrossCursor)
            self.hovered.emit((float(event.xdata), float(event.ydata)))
        else:
            self.canvas.unsetCursor()
            self.hovered.emit(None)
