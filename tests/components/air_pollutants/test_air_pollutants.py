"""The tests for the Air Pollutants component."""
from homeassistant.components.air_pollutants import (
    ATTR_AIR_POLLUTANTS_ATTRIBUTION, ATTR_AIR_POLLUTANTS_N2O,
    ATTR_AIR_POLLUTANTS_OZONE, ATTR_AIR_POLLUTANTS_PM_10)
from homeassistant.setup import async_setup_component


async def test_state(hass):
    """Test Air Pollutants state."""
    config = {
        'air_pollutants': {
            'platform': 'demo',
        }
    }

    assert await async_setup_component(hass, 'air_pollutants', config)

    state = hass.states.get('air_pollutants.demo_air_pollutants_home')
    assert state is not None

    assert state.state == '14'


async def test_attributes(hass):
    """Test Air Pollutants attributes."""
    config = {
        'air_pollutants': {
            'platform': 'demo',
        }
    }

    assert await async_setup_component(hass, 'air_pollutants', config)

    state = hass.states.get('air_pollutants.demo_air_pollutants_office')
    assert state is not None

    data = state.attributes
    assert data.get(ATTR_AIR_POLLUTANTS_PM_10) == 16
    assert data.get(ATTR_AIR_POLLUTANTS_N2O) is None
    assert data.get(ATTR_AIR_POLLUTANTS_OZONE) is None
    assert data.get(ATTR_AIR_POLLUTANTS_ATTRIBUTION) == \
        'Powered by Home Assistant'
