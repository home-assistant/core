"""deCONZ scenes platform tests."""
from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components import deconz

from tests.common import mock_coro


GROUP = {
    "1": {
        "id": "Group id",
        "name": "Group name",
        "state": {},
        "action": {},
        "scenes": [{
            "id": "1",
            "name": "Scene name"
        }],
    }
}

DATA = {"groups": GROUP}


async def setup_bridge(hass):
    """Load the deCONZ scene platform."""
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
    await hass.config_entries.async_forward_entry_setup(config_entry, 'scene')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_scene(hass):
    """Test the update_lights function with some lights."""
    await setup_bridge(hass)
    assert next(iter(hass.data[deconz.DATA_DECONZ_ID])) == \
        "scene.group_name_scene_name"
