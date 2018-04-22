"""deCONZ binary sensor platform tests."""
from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components import deconz

from tests.common import mock_coro


SENSOR = {
    "1": {
        "id": "Sensor id",
        "name": "Sensor name",
        "type": "ZHAPresence",
        "state": {"presence": False},
        "config": {}
    }
}

DATA = {"sensors": SENSOR}


async def setup_bridge(hass):
    """Load the deCONZ binary sensor platform."""
    from pydeconz import DeconzSession
    loop = Mock()
    session = Mock()
    entry = Mock()
    entry.data = {'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF'}
    bridge = DeconzSession(loop, session, **entry.data)
    with patch('pydeconz.DeconzSession.async_get_state',
               return_value=mock_coro(DATA)):
        await bridge.async_load_parameters()
    hass.data[deconz.DOMAIN] = bridge
    hass.data[deconz.DATA_DECONZ_ID] = {}
    config_entry = config_entries.ConfigEntry(1, deconz.DOMAIN, 'Mock Title', {
        'host': 'mock-host'
    }, 'test')
    await hass.config_entries.async_forward_entry_setup(config_entry, 'binary_sensor')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_scene(hass):
    """Test the update_lights function with some lights."""
    await setup_bridge(hass)
    assert next(iter(hass.data[deconz.DATA_DECONZ_ID])) == \
        "binary_sensor.sensor_name"
