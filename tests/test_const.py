"""Test const module."""

from enum import Enum

import pytest

from homeassistant import const

from .common import help_test_all, import_and_test_deprecated_constant


def _create_tuples(
    value: type[Enum] | list[Enum], constant_prefix: str
) -> list[tuple[Enum, str]]:
    return [(enum, constant_prefix) for enum in value]


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(const)


@pytest.mark.parametrize(
    ("replacement", "constant_name", "breaks_in_version"),
    [
        (const.UnitOfArea.SQUARE_METERS, "AREA_SQUARE_METERS", "2025.12"),
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
