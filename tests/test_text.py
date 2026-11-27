# SPDX-License-Identifier: GPL-3.0-or-later
"""Typography of crystallographic indices in the widgets."""

from schmid_explorer.gui.text import pretty

BAR = "̅"


def test_minus_becomes_an_overbar_on_the_right_digits():
    assert pretty("[-1 0 1]") == f"[1{BAR} 0 1]"
    assert pretty("[-1 0 12]") == f"[1{BAR} 0 12]"
    assert pretty("[1 0 -12]") == f"[1 0 1{BAR}2{BAR}]"              # spaced: the whole number
    assert pretty("[-101]") == f"[1{BAR}01]"                           # compact: one digit
    assert pretty("(111)[-101]") == f"(111)[1{BAR}01]"
    assert pretty("{10-11}<11-23>") == f"{{101{BAR}1}}⟨112{BAR}3⟩"
    assert pretty("pyramidal I <c+a>  {10-11}<11-23>  (12)") == f"pyramidal I ⟨c+a⟩  {{101{BAR}1}}⟨112{BAR}3⟩  (12)"
    assert pretty("m = -0.25") == "m = -0.25"                           # numbers are left alone
