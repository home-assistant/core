"""Test the Intelligent Storage Acceleration setup."""

from homeassistant.components.isal import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup(hass: HomeAssistant) -> None:
    """Ensure we can setup."""
    assert await async_setup_component(hass, DOMAIN, {})
