"""The tests for the geo location component."""
from homeassistant.components import geo_location
from homeassistant.setup import async_setup_component


async def test_setup_component(hass):
    """Simple test setup of component."""
    result = await async_setup_component(hass, geo_location.DOMAIN)
    assert result
