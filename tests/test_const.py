"""Test const module."""

from homeassistant import const

from .common import help_test_all


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(const)
