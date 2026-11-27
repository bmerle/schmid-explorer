# SPDX-License-Identifier: GPL-3.0-or-later
"""Smoke test of the GUI without a display (Qt 'offscreen' platform)."""

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from schmid_explorer.core.schmid import PLANE_NORMAL  # noqa: E402
from schmid_explorer.gui.qt import QtWidgets  # noqa: E402
from schmid_explorer.gui.main_window import MainWindow  # noqa: E402
from schmid_explorer.plotting.style import Selection  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture()
def window(app):
    window = MainWindow()
    window.show()
    app.processEvents()
    yield window
    window.close()
    app.processEvents()


def test_start_state_reproduces_the_notebook(window):
    analysis = window.analysis
    assert analysis.structure.key == "fcc"
    assert analysis.loading.indices == (0, 1, 2)
    assert window.table.rowCount() == 12
    assert window.table.item(0, 8).text() == "0.4899"
    assert "2 slip systems" in window.summary.text()
    # tension is the first option and the one selected at the start
    assert analysis.loading.sense == "tension" and window.settings.tension.isChecked()
    assert analysis.results[0].plane == (1, 1, 1) and analysis.results[0].direction == (-1, 0, 1)
    assert "pulls out of the pillar" in window.settings.axis_echo.text()


def test_selection_is_synchronised(window, app):
    best = window.analysis.results[0]
    window.stereo.planeClicked.emit(best.plane_key)
    assert window.selection == Selection(plane=best.plane_key)
    assert len(window.stereo.scene.directions) >= 3          # its glide directions are offered
    window.stereo.directionClicked.emit(best.direction_key)
    assert window.selection == Selection(best.plane_key, best.direction_key)
    assert window.table.selectionModel().selectedRows()[0].row() == 0
    assert window.pillar.slip_slider.isEnabled()
    window.pillar.slip_slider.setValue(60)
    app.processEvents()

    window.table.selectRow(3)                                 # table -> figures
    other = window.analysis.results[3]
    assert window.selection == Selection(other.plane_key, other.direction_key)
    assert window.pillar.slip_slider.value() == 0

    window.stereo.backgroundClicked.emit()
    assert window.selection == Selection()
    assert not window.pillar.slip_slider.isEnabled()


def test_structures_families_and_crss(window, app):
    settings = window.settings
    settings.set_structure("bcc")
    assert window.table.rowCount() == 12
    settings.set_family("bcc_112_111", True)
    settings.set_family("bcc_123_111", True)
    assert window.table.rowCount() == 48

    settings.set_structure("hcp")
    assert window.analysis.lattice.four_index
    assert window.table.rowCount() == 30
    settings.set_axis((0, 0, 1))                              # loading along c
    assert {r.system.family.key for r in window.analysis.primary} == {"hcp_pyr2_ca"}
    assert window.table.isColumnHidden(9)
    settings.use_crss.setChecked(True)
    settings.set_family("hcp_pyr2_ca", True, crss=10.0)
    assert not window.table.isColumnHidden(9)
    assert {r.system.family.key for r in window.analysis.primary} == {"hcp_pyr1_ca"}

    settings.kind.setCurrentIndex(1)                          # axis as plane normal (hkil)
    assert window.analysis.loading.kind == PLANE_NORMAL
    settings.set_tension(False)
    assert window.analysis.loading.sense == "compression"
    app.processEvents()


def test_loading_sense_turns_the_frame_with_the_force(window, app):
    best = window.analysis.results[0]
    window.stereo.planeClicked.emit(best.plane_key)
    window.stereo.directionClicked.emit(best.direction_key)
    pulled = {(r.plane_key, r.direction_key): r for r in window.analysis.results}
    poles = {key: xy for xy, key in window.stereo.scene.poles}
    marks = {key: xy for xy, key in window.stereo.scene.directions}
    shown = [window.table.item(0, column).text() for column in (2, 3)]
    assert np.allclose(window.rotation @ window.analysis.force, [0, 0, 1])

    window.settings.set_tension(False)
    app.processEvents()
    assert "pushes into the pillar" in window.settings.axis_echo.text()
    assert window.selection == Selection(best.plane_key, best.direction_key)    # selection is kept
    # the force is still the centre of the projection: z has turned with it
    assert np.allclose(window.rotation @ window.analysis.force, [0, 0, 1])
    for r in window.analysis.results:
        before = pulled[(r.plane_key, r.direction_key)]
        assert r.m == before.m and r.theta_deg == before.theta_deg
        if before.cos_theta > 0:
            assert r.plane == tuple(-i for i in before.plane)
        if before.cos_lambda > 0:
            assert r.direction == tuple(-i for i in before.direction)
    assert [window.table.item(0, column).text() for column in (2, 3)] != shown
    # the projection is now seen from below the pillar: x is reversed, i.e. mirrored top <-> bottom
    for xy, key in window.stereo.scene.poles:
        if np.hypot(*xy) < 0.999:
            assert np.allclose(xy, poles[key] * [1, -1])
    for xy, key in window.stereo.scene.directions:
        if np.hypot(*xy) < 0.999:
            assert np.allclose(xy, marks[key] * [1, -1])


def test_inverse_pole_figure_follows_the_loading_axis(window, app, tmp_path):
    panel = window.settings.ipf

    def star():
        return panel.figure.axes[0].collections[-1].get_offsets()[0]

    def text():
        return panel.figure.texts[0].get_text()

    start = star()                                            # [012]: on the edge [001]-[011]
    assert np.isclose(start[1], 0) and start[0] > 0 and "equivalent" not in text()
    window.settings.set_tension(False)                        # same point in compression
    assert np.allclose(star(), start)
    window.settings.set_axis((1, 0, 0))                       # <100> is the corner [001]
    assert np.allclose(star(), 0) and "equivalent to $[001]$" in text()
    window.settings.set_axis((2, 1, 0))                       # <012> again
    assert np.allclose(star(), start)

    window.settings.set_structure("hcp")
    assert np.isclose(star()[1], 0)                           # [2 -1 -1 3]: on the edge [0001]-[2-1-10]
    window.settings.set_axis((1, 2, 0))                       # [0 1 -1 0] -> corner [1 0 -1 0]
    assert np.allclose(star(), [np.cos(np.radians(30)), 0.5])

    target = tmp_path / "ipf.png"
    panel.save_image(str(target))
    assert target.stat().st_size > 2000
    panel.copy_image()
    assert not app.clipboard().image().isNull()


def test_auto_view_turns_the_pillar_only_for_another_plane(window, app):
    results = window.analysis.results
    first = results[0]
    same_plane = [r for r in window.analysis.on_plane(first.plane_key) if r.direction_key != first.direction_key]
    other_plane = next(r for r in results if r.plane_key != first.plane_key)
    assert window.pillar.auto_view.isChecked() and len(same_plane) == 2

    window.stereo.planeClicked.emit(first.plane_key)
    view = window.pillar.view
    for result in [first] + same_plane:                       # stepping through the directions of the plane
        window.stereo.directionClicked.emit(result.direction_key)
        assert window.selection == Selection(first.plane_key, result.direction_key)
        assert window.pillar.view == view
    window.table.selectRow(same_plane[0].rank - 1)            # ... also from the table
    assert window.pillar.view == view
    window.settings.set_tension(False)                        # ... and when the load is reversed
    assert window.pillar.view == view

    window.stereo.planeClicked.emit(other_plane.plane_key)    # another plane: the pillar turns
    assert window.pillar.view != view
    window.settings.set_tension(True)
    window.stereo.planeClicked.emit(first.plane_key)
    assert window.pillar.view == view
    window.settings.set_axis((1, 2, 3))                       # another orientation of the crystal
    assert window.pillar.view != view


def test_help_window_shows_every_topic(window, app):
    window.show_help()
    help_window = window.help_window
    titles = [topic.title for topic in help_window.topics]
    assert titles[0] == "Quick start" and "Schmid's law" in titles and "Inverse pole figure" in titles
    for row in range(len(titles)):
        help_window.topic_list.setCurrentRow(row)
        app.processEvents()
        text = help_window.browser.toPlainText()
        assert len(text) > 300 and "<equation>" not in text and "<figure" not in text
    document = help_window.browser.document()
    image = document.resource(document.ResourceType.ImageResource, "help-image-1")
    assert image is not None and not image.isNull()           # equations are stored as images

    window.show_help("Licence and acknowledgements")          # Help -> Licence and acknowledgements
    text = help_window.browser.toPlainText()
    assert "GNU General Public License" in text and "WITHOUT ANY WARRANTY" in text
    for name in ("Python", "Qt 6", "PySide6", "NumPy", "Matplotlib", "PyInstaller", "pycotem"):
        assert name in text
    help_window.close()


def test_help_menu_does_not_link_the_pdf(window):
    entries = [action.text() for menu in window.menuBar().findChildren(QtWidgets.QMenu)
               for action in menu.actions()]
    assert "Schmid Explorer help" in entries and "Licence and acknowledgements" in entries
    assert not any("pdf" in entry.lower() or "documentation" in entry.lower() for entry in entries)


def test_about_names_the_author_and_the_licence(window, monkeypatch):
    shown = {}
    monkeypatch.setattr(QtWidgets.QMessageBox, "about",
                        lambda parent, title, text: shown.update(title=title, text=text))
    window.about()
    assert "Author: Prof. B. Merle, University of Kassel" in shown["text"]
    assert "www.uni-kassel.de/go/mbm" in shown["text"]
    assert "GPL-3.0-or-later" in shown["text"] and "WITHOUT ANY WARRANTY" in shown["text"]


def test_zero_axis_keeps_the_last_result(window):
    before = window.analysis
    window.settings.set_axis((0, 0, 0))
    assert window.analysis is before


def test_exports(window, app, tmp_path):
    window.copy_table()
    text = app.clipboard().text()
    assert "Schmid factor m" in text and "\t" in text

    window.decimal.setCurrentIndex(1)                         # decimal comma -> ';' separated
    path = tmp_path / "table.csv"
    window.export_table(str(path))
    content = path.read_text(encoding="utf-8-sig")
    assert "0,4899" in content and ";" in content and content.startswith("# Schmid Explorer")

    for panel in (window.pillar, window.stereo):
        for suffix in ("png", "svg", "pdf"):
            target = tmp_path / f"{panel.file_stem}.{suffix}"
            panel.save_image(str(target))
            assert target.stat().st_size > 2000
        panel.copy_image()
        assert not app.clipboard().image().isNull()


def test_orientation_map_sets_the_axis(window, app, tmp_path):
    window.show_map()
    dialog = window.map_dialog
    dialog.max_index.setValue(3)
    dialog.panel.clicked.emit(0.0, 0.0)                       # centre of the standard projection
    assert window.analysis.loading.indices == (0, 0, 1)
    assert len(window.analysis.primary) == 8
    dialog.panel.hovered.emit((0.2, 0.1))
    assert "highest m" in dialog.readout.text()
    target = tmp_path / "map.png"
    dialog.panel.save_image(str(target))
    assert target.stat().st_size > 2000
    dialog.close()
