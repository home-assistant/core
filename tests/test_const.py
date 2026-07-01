"""Test const module."""

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
