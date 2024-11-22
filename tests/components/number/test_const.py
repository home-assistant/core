"""Test the number const module."""

import pytest

from homeassistant.components.number import const

from tests.common import help_test_all, import_and_test_deprecated_constant_enum


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(const)


@pytest.mark.parametrize(("enum"), list(const.NumberMode))
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    enum: const.NumberMode,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(caplog, const, enum, "MODE_", "2025.1")
