"""Test qwikswitch sensors."""
import logging

import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.components.qwikswitch import DOMAIN as QWIKSWITCH
from homeassistant.bootstrap import async_setup_component
from tests.test_util.aiohttp import mock_aiohttp_client


_LOGGER = logging.getLogger(__name__)


class AiohttpClientMockResponseList(list):
    """List that fires an event on empty pop, for aiohttp Mocker."""

    def decode(self, _):
        """Return next item from list."""
        try:
            res = list.pop(self)
            _LOGGER.debug("MockResponseList popped %s: %s", res, self)
            return res
        except IndexError:
            _LOGGER.debug("MockResponseList empty")
            return ""

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


async def test_sensor_device(hass, aioclient_mock):
    """Test a sensor device."""
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

    state_obj = hass.states.get('sensor.s1')
    assert state_obj
    assert state_obj.state == 'None'
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    LISTEN.append(  # Close
        """{"id":"@a00001","cmd":"","data":"4e0e1601","rssi":"61%"}""")
    await hass.async_block_till_done()
    state_obj = hass.states.get('sensor.s1')
    assert state_obj.state == 'True'

    # Causes a 30second delay: can be uncommented when upstream library
    # allows cancellation of asyncio.sleep(30) on failed packet ("")
    # LISTEN.append(  # Open
    #     """{"id":"@a00001","cmd":"","data":"4e0e1701","rssi":"61%"}""")
    # await LISTEN.wait_till_empty(hass)
    # state_obj = hass.states.get('sensor.s1')
    # assert state_obj.state == 'False'
