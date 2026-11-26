# SPDX-License-Identifier: GPL-3.0-or-later
"""Small text helpers for the widgets (typography only)."""

from __future__ import annotations

import re

_OVERLINE = "̅"
_BRACKETED = re.compile(r"[\[({<][^\[\](){}<>]*[\])}>]")


def pretty(text: str) -> str:
    """Crystallographic typography: '-1' -> digit with overbar, '<110>' -> angle brackets.

    Inside brackets only. In spaced indices such as '[-1 0 12]' the minus sign belongs to the
    whole number, in compact ones such as '{10-11}' to the next digit.
    """
    def overline(match):
        number = r"-(\d+)" if " " in match.group(0) else r"-(\d)"
        return re.sub(number, lambda minus: "".join(d + _OVERLINE for d in minus.group(1)), match.group(0))

    return _BRACKETED.sub(overline, text).replace("<", "⟨").replace(">", "⟩")
