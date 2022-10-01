"""Test config init."""
from homeassistant.setup import async_setup_component


async def test_config_setup(hass, loop):
    """Test it sets up hassbian."""
    await async_setup_component(hass, "config", {})
    assert "config" in hass.config.components
