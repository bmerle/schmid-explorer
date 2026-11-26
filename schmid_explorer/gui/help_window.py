# SPDX-License-Identifier: GPL-3.0-or-later
"""Help window: list of topics on the left, the text of the selected topic on the right."""

from __future__ import annotations

import re

from .. import APP_NAME
from ..plotting.equation import equation_png, figure_png
from . import help_content
from .qt import Qt, QtCore, QtGui, QtWidgets

_EQUATION = re.compile(r"<equation>(.*?)</equation>", re.DOTALL)
_FIGURE = re.compile(r'<figure name="(\w+)" width="(\d+)"/>')
_STYLE = """
    body { color: #1c1f24; font-size: 10.5pt; }
    h2 { color: #9b0a45; font-size: 15pt; }
    h3 { color: #1c1f24; font-size: 11.5pt; margin-top: 14px; }
    th { background-color: #e9ebee; text-align: left; }
    td, th { border-bottom: 1px solid #c9cdd3; }
    li { margin-bottom: 4px; }
"""


class HelpWindow(QtWidgets.QDialog):
    """Non-modal, so that the help can stay open beside the main window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} – Help")
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.topics = help_content.topics()
        self._pages = {}                    # row -> html with the images resolved
        self._images = 0

        self.topic_list = QtWidgets.QListWidget()
        self.topic_list.addItems([topic.title for topic in self.topics])
        self.topic_list.setFixedWidth(230)
        self.browser = QtWidgets.QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setStyleSheet("QTextBrowser { background: white; padding: 6px; }")
        self.browser.document().setDefaultStyleSheet(_STYLE)
        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(self.close)

        body = QtWidgets.QHBoxLayout()
        body.addWidget(self.topic_list)
        body.addWidget(self.browser, 1)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(body, 1)
        layout.addLayout(buttons)
        self.resize(1040, 780)

        self.topic_list.currentRowChanged.connect(self._show)
        self.topic_list.setCurrentRow(0)

    def show_topic(self, title: str):
        """Select the topic with this title (the first one if there is none)."""
        titles = [topic.title for topic in self.topics]
        self.topic_list.setCurrentRow(titles.index(title) if title in titles else 0)

    # ------------------------------------------------------------------ pages
    def _show(self, row: int):
        if row < 0:
            return
        if row not in self._pages:          # equations and figures are drawn when first needed
            QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self._pages[row] = self._resolve(self.topics[row].html)
            finally:
                QtWidgets.QApplication.restoreOverrideCursor()
        self.browser.setHtml(self._pages[row])

    def _resolve(self, html: str) -> str:
        """Replace the <equation> and <figure> elements by images stored in the document.

        The images are rendered with the pixel density of the screen and shown pixel by pixel:
        scaled images would lose the thin lines of the equations.
        """
        ratio = self.devicePixelRatioF()

        def equation(match):
            return self._image(equation_png(match.group(1), fontsize=12.0, dpi=round(96 * ratio)), ratio)

        def figure(match):
            fig = help_content.FIGURES[match.group(1)]()
            return self._image(figure_png(fig, dpi=int(match.group(2)) * ratio / fig.get_figwidth()), ratio)

        return _FIGURE.sub(figure, _EQUATION.sub(equation, html))

    def _image(self, png: bytes, ratio: float) -> str:
        image = QtGui.QImage.fromData(png, "PNG")
        image.setDevicePixelRatio(ratio)
        self._images += 1
        name = f"help-image-{self._images}"
        self.browser.document().addResource(QtGui.QTextDocument.ResourceType.ImageResource,
                                            QtCore.QUrl(name), image)
        return f'<p align="center"><img src="{name}"></p>'
