"""Test template helper functions."""

import pytest

from homeassistant.helpers.template.helpers import raise_no_default


def test_raise_no_default() -> None:
    """Test raise_no_default raises ValueError with correct message."""
    with pytest.raises(
        ValueError,
        match="Template error: test got invalid input 'invalid' when rendering or compiling template '' but no default was specified",
    ):
        raise_no_default("test", "invalid")
