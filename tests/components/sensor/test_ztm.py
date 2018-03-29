
"""The tests for the tube_state platform."""
import asyncio
from unittest.mock import patch
from datetime import datetime

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.sensor.ztm import (
    ZTMSensor, ZTM_ENDPOINT, ZTM_DATA_ID)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.util.dt as dt_util
from tests.common import load_fixture, assert_setup_component

VALID_CONFIG = {
    'sensor': {
        'platform': 'ztm',
        'name': 'tram',
        'api_key': 'test_api_key',
        'entries': 2,
        'lines': [{
            'number': 24,
            'bus_stop_id':  5068,
            'bus_stop_number': '03'
        }, {
            'number': 23,
            'bus_stop_id':  5068,
            'bus_stop_number': '03'
        }]
    }
}


@asyncio.coroutine
def test_setup_platform(loop, hass):
    """Test generatin two sensors for both tram lines."""
    with assert_setup_component(1):
        yield from async_setup_component(hass, 'sensor', VALID_CONFIG)
    state = hass.states.get('sensor.tram_24_departures_from_5068_03')
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get('departures') == []
    state = hass.states.get('sensor.tram_23_departures_from_5068_03')
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get('departures') == []


@asyncio.coroutine
def test_ztm_data_parsing(hass, aioclient_mock):
    """Test not generating duplicate entity ids with multiple stations."""
    session = async_get_clientsession(hass)
    sensor = ZTMSensor(hass.loop, session, 'test_api', 24, 5068, '03', 'tram',
                       2)
    params = {
        'id': ZTM_DATA_ID,
        'apikey': 'test_api',
        'busstopId': 5068,
        'busstopNr': '03',
        'line': 24,
    }
    aioclient_mock.get(ZTM_ENDPOINT, params=params,
                       text=load_fixture('ztm_valid.json'))
    now = datetime(2015, 9, 15, 5, 44, tzinfo=dt_util.UTC)

    with patch('homeassistant.util.dt.now',
               return_value=now):
        assert sensor.unit_of_measurement == 'min'
        yield from sensor.async_update()
        assert sensor.state == 5
        assert sensor.device_state_attributes['departures'][0] == 5
        assert sensor.device_state_attributes['departures'][1] == 13
        assert len(sensor.device_state_attributes['departures']) == 2
