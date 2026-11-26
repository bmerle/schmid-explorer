# SPDX-License-Identifier: GPL-3.0-or-later
"""Application entry point."""

from __future__ import annotations

import sys

from .. import APP_NAME, __version__


def main(argv=None) -> int:
    from .qt import QtWidgets          # selects the Qt binding and the matplotlib backend
    from .main_window import MainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv if argv is None else argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
