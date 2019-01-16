"""The tests for the utility_meter sensor platform."""
from datetime import timedelta
from unittest.mock import patch
from contextlib import contextmanager

from tests.common import async_fire_time_changed
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, ATTR_ENTITY_ID)
from homeassistant.components.utility_meter import (
    SERVICE_START_PAUSE, SERVICE_RESET)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util


@contextmanager
def alter_time(retval):
    """Manage multiple time mocks."""
    with patch("homeassistant.components."
               "utility_meter.sensor.dt_util.now", return_value=retval):
        yield


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
    with patch('homeassistant.util.dt.utcnow',
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
        'utility_meter': {},
        'sensor': {
            'platform': 'utility_meter',
            'name': 'meter',
            'cycle': 'hourly',
            'source': 'sensor.energy',
        }
    }

    assert await async_setup_component(hass, 'sensor', config)
    assert await async_setup_component(hass, 'utility_meter', config)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    entity_id = config['sensor']['source']
    hass.states.async_set(entity_id, 1, {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 3, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.meter')
    assert state.state == '2'

    # Pause meter - will not meter next period
    data = {ATTR_ENTITY_ID: 'sensor.meter'}
    await hass.services.async_call('utility_meter', SERVICE_START_PAUSE, data)
    await hass.async_block_till_done()

    now += timedelta(seconds=10)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 5, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.meter')
    assert state.state == '2'

    data = {ATTR_ENTITY_ID: 'sensor.meter'}
    await hass.services.async_call('utility_meter', SERVICE_RESET, data)
    await hass.async_block_till_done()

    state = hass.states.get('sensor.meter')
    assert state.state == '0'


async def _test_self_reset(hass, cycle, start_time, expect_reset=True):
    """Test energy sensor self reset."""
    config = {
        'sensor': {
            'platform': 'utility_meter',
            'name': 'meter',
            'cycle': cycle,
            'source': 'sensor.energy',
        }
    }

    entity_id = config['sensor']['source']

    now = dt_util.parse_datetime(start_time)
    with alter_time(now):
        assert await async_setup_component(hass, 'sensor', config)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

        async_fire_time_changed(hass, now)
        hass.states.async_set(entity_id, 1, {"unit_of_measurement": "kWh"})
        await hass.async_block_till_done()

    now += timedelta(seconds=30)
    with alter_time(now):
        async_fire_time_changed(hass, now)
        hass.states.async_set(entity_id, 3, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    now += timedelta(seconds=30)
    with alter_time(now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        hass.states.async_set(entity_id, 6, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.meter')
    if expect_reset:
        assert state.attributes.get('last_period') == '2'
        assert state.state == '3'
    else:
        assert state.attributes.get('last_period') == 0
        assert state.state == '5'


async def test_self_reset_hourly(hass):
    """Test hourly reset of meter."""
    await _test_self_reset(hass, 'hourly', "2017-12-31T23:59:00.000000+00:00")


async def test_self_reset_daily(hass):
    """Test daily reset of meter."""
    await _test_self_reset(hass, 'daily', "2017-12-31T23:59:00.000000+00:00")


async def test_self_reset_weekly(hass):
    """Test weekly reset of meter."""
    await _test_self_reset(hass, 'weekly', "2017-12-31T23:59:00.000000+00:00")


async def test_self_reset_monthly(hass):
    """Test monthly reset of meter."""
    await _test_self_reset(hass, 'monthly', "2017-12-31T23:59:00.000000+00:00")


async def test_self_reset_yearly(hass):
    """Test yearly reset of meter."""
    await _test_self_reset(hass, 'yearly', "2017-12-31T23:59:00.000000+00:00")


async def test_self_no_reset_yearly(hass):
    """Test yearly reset of meter does not occur after 1st January."""
    await _test_self_reset(hass, 'yearly', "2018-01-01T23:59:00.000000+00:00",
                           expect_reset=False)
