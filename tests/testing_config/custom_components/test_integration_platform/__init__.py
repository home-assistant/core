"""Provide a mock package component."""

from .const import TEST  # noqa: F401

DOMAIN = "test_integration_platform"


async def async_setup(hass, config):
    """Mock a successful setup."""
    return True
