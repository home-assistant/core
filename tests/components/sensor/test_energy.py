"""The tests for the energy sensor platform."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util


async def test_state(hass):
    """Test energy sensor state."""
    config = {
        'sensor': {
            'platform': 'energy',
            'name': 'energy',
            'source': 'sensor.power',
            'round': 2
        }
    }

    assert await async_setup_component(hass, 'sensor', config)

    entity_id = config['sensor']['source']
    hass.states.async_set(entity_id, 1000, {"unit_of_measurement": "W"})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=3600)
    with patch('homeassistant.helpers.condition.dt_util.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 1000, {"unit_of_measurement": "W"},
                              force_update=True)
        await hass.async_block_till_done()

        state = hass.states.get('sensor.energy')
        assert state is not None

        # 1000 Watts for 1hour = 1kWh
        assert round(float(state.state), config['sensor']['round']) == 1.0


async def test_power_source(hass):
    """Test energy sensor state using a power source."""
    config = {
        'sensor': {
            'platform': 'energy',
            'name': 'energy',
            'source': 'sensor.power',
            'round': 2
        }
    }

    assert await async_setup_component(hass, 'sensor', config)

    entity_id = config['sensor']['source']
    hass.states.async_set(entity_id, 1, {"unit_of_measurement": "kW"})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=3600)
    with patch('homeassistant.helpers.condition.dt_util.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 1, {"unit_of_measurement": "kW"},
                              force_update=True)
        await hass.async_block_till_done()

        state = hass.states.get('sensor.energy')
        assert state is not None

        # 1 KiloWatt for 1hour = 1kWh
        assert round(float(state.state), config['sensor']['round']) == 1.0
