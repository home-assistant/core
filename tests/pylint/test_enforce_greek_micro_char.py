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
            # Test using the correct μ-sign \u03bc with annotation
            """
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER: Final = "μg/m³"
        """,
            id="good_const_with_annotation",
        ),
        pytest.param(
            # Test using the correct μ-sign \u03bc with annotation using unicode encoding
            """
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER: Final = "\u03bcg/m³"
        """,
            id="good_unicode_const_with_annotation",
        ),
        pytest.param(
            # Test using the correct μ-sign \u03bc without annotation
            """
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = "μg/m³"
        """,
            id="good_const_without_annotation",
        ),
        pytest.param(
            # Test using the correct μ-sign \u03bc in a StrEnum class
            """
            class UnitOfElectricPotential(StrEnum):
                \"\"\"Electric potential units.\"\"\"

                MICROVOLT = "μV"
                MILLIVOLT = "mV"
                VOLT = "V"
                KILOVOLT = "kV"
                MEGAVOLT = "MV"
        """,
            id="good_str_enum",
        ),
        pytest.param(
            # Test using the correct μ-sign \u03bc in a sensor description dict
            """
            SENSOR_DESCRIPTION = {
                "radiation_rate": AranetSensorEntityDescription(
                    key="radiation_rate",
                    translation_key="radiation_rate",
                    name="Radiation Dose Rate",
                    native_unit_of_measurement="μSv/h",
                    state_class=SensorStateClass.MEASUREMENT,
                    suggested_display_precision=2,
                    scale=0.001,
                ),
            }
            OTHER_DICT = {
                "value_with_bad_mu_should_pass": "µ"
            }
        """,
            id="good_sensor_description",
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
            # Test we can detect the legacy coding of μ \u00b5
            # instead of recommended coding of μ \u03bc" with annotation
            """
            CONCENTRATION_MICROGRAMS_PER_CUBIC_METER: Final = "µg/m³"
        """,
            id="bad_const_with_annotation",
        ),
        pytest.param(
            # Test we can detect the unicode variant of the legacy coding of μ \u00b5
            # instead of recommended coding of μ \u03bc" with annotation
            """
            CONCENTRATION_MICROGRAMS_PER_CUBIC_METER: Final = "\u00b5g/m³"
        """,
            id="bad_unicode_const_with_annotation",
        ),
        pytest.param(
            # Test we can detect the legacy coding of μ \u00b5
            # instead of recommended coding of μ \u03bc" without annotation
            """
            CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = "µg/m³"
        """,
            id="bad_const_without_annotation",
        ),
        pytest.param(
            # Test we can detect the legacy coding of μ \u00b5
            # instead of recommended coding of μ \u03bc" in a StrEnum class
            """
            class UnitOfElectricPotential(StrEnum):
                \"\"\"Electric potential units.\"\"\"

                MICROVOLT = "µV"
                MILLIVOLT = "mV"
                VOLT = "V"
                KILOVOLT = "kV"
                MEGAVOLT = "MV"
        """,
            id="bad_str_enum",
        ),
        pytest.param(
            # Test we can detect the legacy coding of μ \u00b5
            # instead of recommended coding of μ \u03bc" in a sensor description dict
            """
            SENSOR_DESCRIPTION = {
                "radiation_rate": AranetSensorEntityDescription(
                    key="radiation_rate",
                    translation_key="radiation_rate",
                    name="Radiation Dose Rate",
                    native_unit_of_measurement="µSv/h",
                    state_class=SensorStateClass.MEASUREMENT,
                    suggested_display_precision=2,
                    scale=0.001,
                ),
            }
        """,
            id="bad_sensor_description",
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
