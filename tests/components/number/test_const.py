"""Test the number const module."""

import pytest

from homeassistant.components.number import const

from tests.common import import_and_test_deprecated_constant_enum


@pytest.mark.parametrize(("enum"), list(const.NumberMode))
def test_deprecated_constants(
    caplog: pytest.LogCaptureFixture,
    enum: const.NumberMode,
) -> None:
    """Test deprecated constants."""
    import_and_test_deprecated_constant_enum(caplog, const, enum, "MODE_", "2025.1")
