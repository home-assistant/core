"""Test qwikswitch sensors."""
import logging

import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.components.qwikswitch import DOMAIN as QWIKSWITCH
from homeassistant.bootstrap import async_setup_component
from tests.test_util.aiohttp import mock_aiohttp_client


_LOGGER = logging.getLogger(__name__)


class AiohttpClientMockResponseList(list):
    """Return multiple values for aiohttp Mocker.

    aoihttp mocker uses decode to fetch the next value.
    """

    def decode(self, _):
        """Return next item from list."""
        try:
            res = list.pop(self, 0)
            _LOGGER.debug("MockResponseList popped %s: %s", res, self)
            return res
        except IndexError:
            raise AssertionError("MockResponseList empty")

    async def wait_till_empty(self, hass):
        """Wait until empty."""
        while self:
            await hass.async_block_till_done()
        await hass.async_block_till_done()


LISTEN = AiohttpClientMockResponseList()


@pytest.fixture
def aioclient_mock():
    """HTTP client listen and devices."""
    devices = """[
        {"id":"@000001","name":"Switch 1","type":"rel","val":"OFF",
        "time":"1522777506","rssi":"51%"},
        {"id":"@000002","name":"Light 2","type":"rel","val":"ON",
        "time":"1522777507","rssi":"45%"},
        {"id":"@000003","name":"Dim 3","type":"dim","val":"280c00",
        "time":"1522777544","rssi":"62%"}]"""

    with mock_aiohttp_client() as mock_session:
        mock_session.get("http://127.0.0.1:2020/&listen", content=LISTEN)
        mock_session.get("http://127.0.0.1:2020/&device", text=devices)
        yield mock_session


async def test_binary_sensor_device(hass, aioclient_mock):
    """Test a binary sensor device."""
    config = {
        'qwikswitch': {
            'sensors': {
                'name': 's1',
                'id': '@a00001',
                'channel': 1,
                'type': 'imod',
            }
        }
    }
    await async_setup_component(hass, QWIKSWITCH, config)
    await hass.async_block_till_done()

    state_obj = hass.states.get('binary_sensor.s1')
    assert state_obj.state == 'off'

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    LISTEN.append('{"id":"@a00001","cmd":"","data":"4e0e1601","rssi":"61%"}')
    LISTEN.append('')  # Will cause a sleep
    await hass.async_block_till_done()
    state_obj = hass.states.get('binary_sensor.s1')
    assert state_obj.state == 'on'

    LISTEN.append('{"id":"@a00001","cmd":"","data":"4e0e1701","rssi":"61%"}')
    hass.data[QWIKSWITCH]._sleep_task.cancel()
    await LISTEN.wait_till_empty(hass)
    state_obj = hass.states.get('binary_sensor.s1')
    assert state_obj.state == 'off'


async def test_sensor_device(hass, aioclient_mock):
    """Test a sensor device."""
    config = {
        'qwikswitch': {
            'sensors': {
                'name': 'ss1',
                'id': '@a00001',
                'channel': 1,
                'type': 'qwikcord',
            }
        }
    }
    await async_setup_component(hass, QWIKSWITCH, config)
    await hass.async_block_till_done()

    state_obj = hass.states.get('sensor.ss1')
    assert state_obj.state == 'None'

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    LISTEN.append(
        '{"id":"@a00001","name":"ss1","type":"rel",'
        '"val":"4733800001a00000"}')
    LISTEN.append('')  # Will cause a sleep
    await LISTEN.wait_till_empty(hass)  # await hass.async_block_till_done()

    state_obj = hass.states.get('sensor.ss1')
    assert state_obj.state == 'None'
