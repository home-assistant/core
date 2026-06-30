"""Test const module."""

import pytest

from homeassistant import const
from homeassistant.const import UnitOfDensity, UnitOfRatio

from .common import (
    help_test_all,
    import_and_test_deprecated_constant,
    import_and_test_deprecated_constant_enum,
)


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(const)


@pytest.mark.parametrize(
    ("replacement", "constant_name", "breaks_in_version"),
    [
        (
            "p/m³",
            "CONCENTRATION_PARTS_PER_CUBIC_METER",
            "2027.7",
        ),
    ],
)
def test_deprecated_constant(
    caplog: pytest.LogCaptureFixture,
    replacement: str,
    constant_name: str,
    breaks_in_version: str,
) -> None:
    """Test deprecated constants, where no replacement is provided."""
    import_and_test_deprecated_constant(
        caplog,
        const,
        constant_name,
        replacement,
        replacement,
        breaks_in_version,
    )


@pytest.mark.parametrize(
    "replacement",
    [
        UnitOfDensity.GRAMS_PER_CUBIC_METER,
        UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER,
        UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        UnitOfDensity.MICROGRAMS_PER_CUBIC_FOOT,
        UnitOfRatio.PARTS_PER_MILLION,
        UnitOfRatio.PARTS_PER_BILLION,
    ],
)
def test_deprecated_concentration_constant(
    caplog: pytest.LogCaptureFixture,
    replacement: UnitOfDensity | UnitOfRatio,
) -> None:
    """Test deprecated concentration constants replaced by an enum."""
    import_and_test_deprecated_constant_enum(
        caplog,
        const,
        replacement,
        "CONCENTRATION_",
        "2027.8",
    )
