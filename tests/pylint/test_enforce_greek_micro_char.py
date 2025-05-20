"""Tests for pylint hass_enforce_greek_micro_char plugin."""

from __future__ import annotations

import astroid
from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
import pytest

from . import assert_no_messages


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER: Final = "μg/m³"  # "μ" == "\u03bc"
        """,
            id="good_const_with_annotation",
        ),
        pytest.param(
            """
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER: Final = "\u03bcg/m³"  # "μ" == "\u03bc"
        """,
            id="good_unicode_const_with_annotation",
        ),
        pytest.param(
            """
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = "μg/m³"  # "μ" == "\u03bc"
        """,
            id="good_const_without_annotation",
        ),
        pytest.param(
            """
            class UnitOfElectricPotential(StrEnum):
                \"\"\"Electric potential units.\"\"\"

                MICROVOLT = "μV"  # "μ" == "\u03bc"
                MILLIVOLT = "mV"
                VOLT = "V"
                KILOVOLT = "kV"
                MEGAVOLT = "MV"
        """,
            id="good_str_enum",
        ),
    ],
)
def test_enforce_greek_micro_char(
    linter: UnittestLinter,
    enforce_greek_micro_char_checker: BaseChecker,
    code: str,
) -> None:
    """Good test cases."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_greek_micro_char_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
            CONCENTRATION_MICROGRAMS_PER_CUBIC_METER: Final = "µg/m³"  # "μ" != "\u03bc"
        """,
            id="bad_const_with_annotation",
        ),
        pytest.param(
            """
            CONCENTRATION_MICROGRAMS_PER_CUBIC_METER: Final = "\u00b5g/m³"  # "μ" != "\u03bc"
        """,
            id="bad_unicode_const_with_annotation",
        ),
        pytest.param(
            """
            CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = "µg/m³"  # "μ" != "\u03bc"
        """,
            id="bad_const_without_annotation",
        ),
        pytest.param(
            """
            class UnitOfElectricPotential(StrEnum):
                \"\"\"Electric potential units.\"\"\"

                MICROVOLT = "µV"  # "μ" != "\u03bc"
                MILLIVOLT = "mV"
                VOLT = "V"
                KILOVOLT = "kV"
                MEGAVOLT = "MV"
        """,
            id="bad_str_enum",
        ),
    ],
)
def test_enforce_greek_micro_char_assign_bad(
    linter: UnittestLinter,
    enforce_greek_micro_char_checker: BaseChecker,
    code: str,
) -> None:
    """Bad assignment test cases."""
    root_node = astroid.parse(code, "homeassistant.components.pylint_test")
    walker = ASTWalker(linter)
    walker.add_checker(enforce_greek_micro_char_checker)

    walker.walk(root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    message = next(iter(messages))
    assert message.msg_id == "hass-enforce-greek-micro-char"
