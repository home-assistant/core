"""Test const module."""

from enum import Enum

import pytest

from homeassistant import const

from .common import help_test_all, import_and_test_deprecated_constant


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(const)


@pytest.mark.parametrize(
    ("replacement", "constant_name", "breaks_in_version"),
    [
        (
            const.UnitOfDensity.GRAMS_PER_CUBIC_METER,
            "CONCENTRATION_GRAMS_PER_CUBIC_METER",
            "2027.7",
        ),
        (
            const.UnitOfDensity.MICROGRAMS_PER_CUBIC_FOOT,
            "CONCENTRATION_MICROGRAMS_PER_CUBIC_FOOT",
            "2027.7",
        ),
        (
            const.UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
            "CONCENTRATION_MICROGRAMS_PER_CUBIC_METER",
            "2027.7",
        ),
        (
            const.UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER,
            "CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER",
            "2027.7",
        ),
    ],
)
def test_deprecated_constant_name_changes(
    caplog: pytest.LogCaptureFixture,
    replacement: Enum,
    constant_name: str,
    breaks_in_version: str,
) -> None:
    """Test deprecated constants, where the name is not the same as the enum value."""
    import_and_test_deprecated_constant(
        caplog,
        const,
        constant_name,
        f"{replacement.__class__.__name__}.{replacement.name}",
        replacement,
        breaks_in_version,
    )
