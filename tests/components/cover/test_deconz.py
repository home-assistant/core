"""deCONZ cover platform tests."""
from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.components.deconz.const import COVER_TYPES
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import mock_coro

SUPPORTED_COVERS = {
    "1": {
        "id": "Cover 1 id",
        "name": "Cover 1 name",
        "type": "Level controllable output",
        "state": {}
    }
}

UNSUPPORTED_COVER = {
    "1": {
        "id": "Cover id",
        "name": "Unsupported switch",
        "type": "Not a cover",
        "state": {}
    }
}


async def setup_bridge(hass, data):
    """Load the deCONZ cover platform."""
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
    hass.data[deconz.DATA_DECONZ_UNSUB] = []
    hass.data[deconz.DATA_DECONZ_ID] = {}
    config_entry = config_entries.ConfigEntry(
        1, deconz.DOMAIN, 'Mock Title', {'host': 'mock-host'}, 'test',
        config_entries.CONN_CLASS_LOCAL_PUSH)
    await hass.config_entries.async_forward_entry_setup(config_entry, 'cover')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_no_switches(hass):
    """Test that no cover entities are created."""
    data = {}
    await setup_bridge(hass, data)
    assert len(hass.data[deconz.DATA_DECONZ_ID]) == 0
    assert len(hass.states.async_all()) == 0


async def test_cover(hass):
    """Test that all supported cover entities are created."""
    await setup_bridge(hass, {"lights": SUPPORTED_COVERS})
    assert "cover.cover_1_name" in hass.data[deconz.DATA_DECONZ_ID]
    assert len(SUPPORTED_COVERS) == len(COVER_TYPES)
    assert len(hass.states.async_all()) == 2


async def test_add_new_cover(hass):
    """Test successful creation of cover entity."""
    data = {}
    await setup_bridge(hass, data)
    cover = Mock()
    cover.name = 'name'
    cover.type = "Level controllable output"
    cover.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_light', [cover])
    await hass.async_block_till_done()
    assert "cover.name" in hass.data[deconz.DATA_DECONZ_ID]


async def test_unsupported_cover(hass):
    """Test that unsupported covers are not created."""
    await setup_bridge(hass, {"lights": UNSUPPORTED_COVER})
    assert len(hass.states.async_all()) == 0
