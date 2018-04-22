"""deCONZ binary sensor platform tests."""
from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components import deconz

from tests.common import mock_coro


SENSOR = {
    "1": {
        "id": "Sensor 1 id",
        "name": "Sensor 1 name",
        "type": "ZHAPresence",
        "state": {"presence": False},
        "config": {}
    }
}


async def setup_bridge(hass, data):
    """Load the deCONZ binary sensor platform."""
    from pydeconz import DeconzSession
    loop = Mock()
    session = Mock()
    entry = Mock()
    entry.data = {'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF'}
    bridge = DeconzSession(loop, session, **entry.data)
    with patch('pydeconz.DeconzSession.async_get_state',
               return_value=mock_coro(data)):
        await bridge.async_load_parameters()
    hass.data[deconz.DOMAIN] = bridge
    hass.data[deconz.DATA_DECONZ_ID] = {}
    config_entry = config_entries.ConfigEntry(
        1, deconz.DOMAIN, 'Mock Title', {'host': 'mock-host'}, 'test')
    await hass.config_entries.async_forward_entry_setup(
        config_entry, 'binary_sensor')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_no_binary_sensors(hass):
    """Test the update_lights function with some lights."""
    data = {}
    await setup_bridge(hass, data)
    assert len(hass.data[deconz.DATA_DECONZ_ID]) == 0
    assert len(hass.states.async_all()) == 0


async def test_binary_sensors(hass):
    """Test the update_lights function with some lights."""
    data = {"sensors": SENSOR}
    await setup_bridge(hass, data)
    assert "binary_sensor.sensor_1_name" in hass.data[deconz.DATA_DECONZ_ID]
    assert len(hass.states.async_all()) == 1
