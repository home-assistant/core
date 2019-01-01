"""The tests for the energy sensor platform."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, ATTR_ENTITY_ID)
from homeassistant.components.sensor.utility_meter import (
    SERVICE_START_PAUSE, SERVICE_RESET)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util


async def test_state(hass):
    """Test utility sensor state."""
    config = {
        'sensor': {
            'platform': 'utility_meter',
            'name': 'meter',
            'source': 'sensor.energy',
        }
    }

    assert await async_setup_component(hass, 'sensor', config)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    entity_id = config['sensor']['source']
    hass.states.async_set(entity_id, 2, {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with patch('homeassistant.helpers.condition.dt_util.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 3, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

        state = hass.states.get('sensor.meter')
        assert state is not None

        assert state.state == '1'


async def test_services(hass):
    """Test energy sensor reset service."""
    config = {
        'sensor': {
            'platform': 'utility_meter',
            'name': 'meter',
            'cycle': 'hourly',
            'source': 'sensor.energy',
        }
    }

    assert await async_setup_component(hass, 'sensor', config)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    entity_id = config['sensor']['source']
    hass.states.async_set(entity_id, 1, {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with patch('homeassistant.helpers.condition.dt_util.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 3, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.meter')
    assert state.state == '2'

    # Pause meter - will not meter next period
    data = {ATTR_ENTITY_ID: 'sensor.meter'}
    await hass.services.async_call('sensor', SERVICE_START_PAUSE, data)
    await hass.async_block_till_done()

    now += timedelta(seconds=10)
    with patch('homeassistant.helpers.condition.dt_util.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 5, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.meter')
    assert state.state == '2'

    data = {ATTR_ENTITY_ID: 'sensor.meter'}
    await hass.services.async_call('sensor', SERVICE_RESET, data)
    await hass.async_block_till_done()

    state = hass.states.get('sensor.meter')
    assert state.state == '0'
