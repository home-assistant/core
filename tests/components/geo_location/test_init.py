"""The tests for the geo location component."""
from homeassistant.components import geo_location
from homeassistant.components.geo_location import GeoLocationEvent
from homeassistant.setup import async_setup_component


async def test_setup_component(hass):
    """Simple test setup of component."""
    result = await async_setup_component(hass, geo_location.DOMAIN)
    assert result


async def test_event(hass):
    """Simple test of the geo location event class."""
    entity = GeoLocationEvent()

    assert entity.state is None
    assert entity.distance is None
    assert entity.latitude is None
    assert entity.longitude is None
