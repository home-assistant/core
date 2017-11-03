"""Tests for Vanderbilt SPC component."""
import asyncio

import pytest

from homeassistant.components import spc
from homeassistant.bootstrap import async_setup_component
from tests.common import async_test_home_assistant
from tests.test_util.aiohttp import mock_aiohttp_client
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED)


@pytest.fixture
def hass(loop):
    """Home Assistant fixture with device mapping registry."""
    hass = loop.run_until_complete(async_test_home_assistant(loop))
    hass.data[spc.DATA_REGISTRY] = spc.SpcRegistry()
    hass.data[spc.DATA_API] = None
    yield hass
    loop.run_until_complete(hass.async_stop())


@pytest.fixture
def spcwebgw(hass):
    """Fixture for the SPC Web Gateway API configured for localhost."""
    yield spc.SpcWebGateway(hass=hass,
                            api_url='http://localhost/',
                            ws_url='ws://localhost/')


@pytest.fixture
def aioclient_mock():
    """HTTP client mock for areas and zones."""
    areas = """{"status":"success","data":{"area":[{"id":"1","name":"House",
    "mode":"0","last_set_time":"1485759851","last_set_user_id":"1",
    "last_set_user_name":"Pelle","last_unset_time":"1485800564",
    "last_unset_user_id":"1","last_unset_user_name":"Pelle","last_alarm":
    "1478174896"},{"id":"3","name":"Garage","mode":"0","last_set_time":
    "1483705803","last_set_user_id":"9998","last_set_user_name":"Lisa",
    "last_unset_time":"1483705808","last_unset_user_id":"9998",
    "last_unset_user_name":"Lisa"}]}}"""

    zones = """{"status":"success","data":{"zone":[{"id":"1","type":"3",
    "zone_name":"Kitchen smoke","area":"1","area_name":"House","input":"0",
    "logic_input":"0","status":"0","proc_state":"0","inhibit_allowed":"1",
    "isolate_allowed":"1"},{"id":"3","type":"0","zone_name":"Hallway PIR",
    "area":"1","area_name":"House","input":"0","logic_input":"0","status":
    "0","proc_state":"0","inhibit_allowed":"1","isolate_allowed":"1"},
    {"id":"5","type":"1","zone_name":"Front door","area":"1","area_name":
    "House","input":"1","logic_input":"0","status":"0","proc_state":"0",
    "inhibit_allowed":"1","isolate_allowed":"1"}]}}"""

    with mock_aiohttp_client() as mock_session:
        mock_session.get('http://localhost/spc/area', text=areas)
        mock_session.get('http://localhost/spc/zone', text=zones)
        yield mock_session


@asyncio.coroutine
@pytest.mark.parametrize("sia_code,state", [
    ('NL', STATE_ALARM_ARMED_HOME),
    ('CG', STATE_ALARM_ARMED_AWAY),
    ('OG', STATE_ALARM_DISARMED)
])
def test_update_alarm_device(hass, aioclient_mock, monkeypatch,
                             sia_code, state):
    """Test that alarm panel state changes on incoming websocket data."""
    monkeypatch.setattr("homeassistant.components.spc.SpcWebGateway."
                        "start_listener", lambda x, *args: None)
    config = {
        'spc': {
            'api_url': 'http://localhost/',
            'ws_url': 'ws://localhost/'
        }
    }
    yield from async_setup_component(hass, 'spc', config)
    yield from hass.async_block_till_done()

    entity_id = 'alarm_control_panel.house'

    assert hass.states.get(entity_id).state == STATE_ALARM_DISARMED

    msg = {"sia_code": sia_code, "sia_address": "1",
           "description": "House¦Sam¦1"}
    yield from spc._async_process_message(msg, hass.data[spc.DATA_REGISTRY])
    yield from hass.async_block_till_done()

    state_obj = hass.states.get(entity_id)
    assert state_obj.state == state
    assert state_obj.attributes['changed_by'] == 'Sam'


@asyncio.coroutine
@pytest.mark.parametrize("sia_code,state", [
    ('ZO', STATE_ON),
    ('ZC', STATE_OFF)
])
def test_update_sensor_device(hass, aioclient_mock, monkeypatch,
                              sia_code, state):
    """
    Test that sensors change state on incoming websocket data.

    Note that we don't test for the ZD (disconnected) and ZX (problem/short)
    codes since the binary sensor component is hardcoded to only
    let on/off states through.
    """
    monkeypatch.setattr("homeassistant.components.spc.SpcWebGateway."
                        "start_listener", lambda x, *args: None)
    config = {
        'spc': {
            'api_url': 'http://localhost/',
            'ws_url': 'ws://localhost/'
        }
    }
    yield from async_setup_component(hass, 'spc', config)
    yield from hass.async_block_till_done()

    assert hass.states.get('binary_sensor.hallway_pir').state == STATE_OFF

    msg = {"sia_code": sia_code, "sia_address": "3",
           "description": "Hallway PIR"}
    yield from spc._async_process_message(msg, hass.data[spc.DATA_REGISTRY])
    yield from hass.async_block_till_done()
    assert hass.states.get('binary_sensor.hallway_pir').state == state


class TestSpcRegistry:
    """Test the device mapping registry."""

    def test_sensor_device(self):
        """Test retrieving device based on ID."""
        r = spc.SpcRegistry()
        r.register_sensor_device('1', 'dummy')
        assert r.get_sensor_device('1') == 'dummy'

    def test_alarm_device(self):
        """Test retrieving device based on zone name."""
        r = spc.SpcRegistry()
        r.register_alarm_device('Area 51', 'dummy')
        assert r.get_alarm_device('Area 51') == 'dummy'


class TestSpcWebGateway:
    """Test the SPC Web Gateway API wrapper."""

    @asyncio.coroutine
    def test_get_areas(self, spcwebgw, aioclient_mock):
        """Test area retrieval."""
        result = yield from spcwebgw.get_areas()
        assert aioclient_mock.call_count == 1
        assert len(list(result)) == 2

    @asyncio.coroutine
    @pytest.mark.parametrize("url_command,command", [
        ('set', spc.SpcWebGateway.AREA_COMMAND_SET),
        ('unset', spc.SpcWebGateway.AREA_COMMAND_UNSET),
        ('set_a', spc.SpcWebGateway.AREA_COMMAND_PART_SET)
    ])
    def test_area_commands(self, spcwebgw, url_command, command):
        """Test alarm arming/disarming."""
        with mock_aiohttp_client() as aioclient_mock:
            url = "http://localhost/spc/area/1/{}".format(url_command)
            aioclient_mock.put(url, text='{}')
            yield from spcwebgw.send_area_command('1', command)
            assert aioclient_mock.call_count == 1
