"""The tests for the integration sensor platform."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util


async def test_state(hass):
    """Test integration sensor state."""
    config = {
        'sensor': {
            'platform': 'integration',
            'name': 'integration',
            'source': 'sensor.power',
            'unit': 'kWh',
            'round': 2,
        }
    }

    assert await async_setup_component(hass, 'sensor', config)

    entity_id = config['sensor']['source']
    hass.states.async_set(entity_id, 1, {})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=3600)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 1, {}, force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.integration')
    assert state is not None

    # Testing a power sensor at 1 KiloWatts for 1hour = 1kWh
    assert round(float(state.state), config['sensor']['round']) == 1.0

    assert state.attributes.get('unit_of_measurement') == 'kWh'


async def test_prefix(hass):
    """Test integration sensor state using a power source."""
    config = {
        'sensor': {
            'platform': 'integration',
            'name': 'integration',
            'source': 'sensor.power',
            'round': 2,
            'unit_prefix': 'k'
        }
    }

    assert await async_setup_component(hass, 'sensor', config)

    entity_id = config['sensor']['source']
    hass.states.async_set(entity_id, 1000, {'unit_of_measurement': 'W'})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=3600)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 1000, {'unit_of_measurement': 'W'},
                              force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.integration')
    assert state is not None

    # Testing a power sensor at 1000 Watts for 1hour = 1kWh
    assert round(float(state.state), config['sensor']['round']) == 1.0
    assert state.attributes.get('unit_of_measurement') == 'kWh'


async def test_suffix(hass):
    """Test integration sensor state using a network counter source."""
    config = {
        'sensor': {
            'platform': 'integration',
            'name': 'integration',
            'source': 'sensor.bytes_per_second',
            'round': 2,
            'unit_prefix': 'k',
            'unit_time': 's'
        }
    }

    assert await async_setup_component(hass, 'sensor', config)

    entity_id = config['sensor']['source']
    hass.states.async_set(entity_id, 1000, {})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 1000, {}, force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.integration')
    assert state is not None

    # Testing a network speed sensor at 1000 bytes/s over 10s  = 10kbytes
    assert round(float(state.state), config['sensor']['round']) == 10.0
