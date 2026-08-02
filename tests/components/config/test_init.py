"""Test config init."""

from homeassistant.components.config import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_config_setup(hass: HomeAssistant) -> None:
    """Test it sets up hassbian."""
    await async_setup_component(hass, DOMAIN, {})
    assert "config" in hass.config.components
