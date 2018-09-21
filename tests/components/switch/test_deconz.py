"""deCONZ switch platform tests."""
from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.components.deconz.const import SWITCH_TYPES
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import mock_coro

SUPPORTED_SWITCHES = {
    "1": {
        "id": "Switch 1 id",
        "name": "Switch 1 name",
        "type": "On/Off plug-in unit",
        "state": {}
    },
    "2": {
        "id": "Switch 2 id",
        "name": "Switch 2 name",
        "type": "Smart plug",
        "state": {}
    },
    "3": {
        "id": "Switch 3 id",
        "name": "Switch 3 name",
        "type": "Warning device",
        "state": {}
    }
}

UNSUPPORTED_SWITCH = {
    "1": {
        "id": "Switch id",
        "name": "Unsupported switch",
        "type": "Not a smart plug",
        "state": {}
    }
}


async def setup_bridge(hass, data):
    """Load the deCONZ switch platform."""
    from pydeconz import DeconzSession
    loop = Mock()
    session = Mock()
    entry = Mock()
    entry.data = {'host': '1.2.3.4', 'port': 80, 'api_key': '1234567890ABCDEF'}
    bridge = DeconzSession(loop, session, **entry.data)
    bridge.config = Mock()
    with patch('pydeconz.DeconzSession.async_get_state',
               return_value=mock_coro(data)):
        await bridge.async_load_parameters()
    hass.data[deconz.DOMAIN] = bridge
    hass.data[deconz.DATA_DECONZ_UNSUB] = []
    hass.data[deconz.DATA_DECONZ_ID] = {}
    config_entry = config_entries.ConfigEntry(
        1, deconz.DOMAIN, 'Mock Title', {'host': 'mock-host'}, 'test',
        config_entries.CONN_CLASS_LOCAL_PUSH)
    await hass.config_entries.async_forward_entry_setup(config_entry, 'switch')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_no_switches(hass):
    """Test that no switch entities are created."""
    data = {}
    await setup_bridge(hass, data)
    assert len(hass.data[deconz.DATA_DECONZ_ID]) == 0
    assert len(hass.states.async_all()) == 0


async def test_switch(hass):
    """Test that all supported switch entities are created."""
    await setup_bridge(hass, {"lights": SUPPORTED_SWITCHES})
    assert "switch.switch_1_name" in hass.data[deconz.DATA_DECONZ_ID]
    assert "switch.switch_2_name" in hass.data[deconz.DATA_DECONZ_ID]
    assert "switch.switch_3_name" in hass.data[deconz.DATA_DECONZ_ID]
    assert len(SUPPORTED_SWITCHES) == len(SWITCH_TYPES)
    assert len(hass.states.async_all()) == 4


async def test_add_new_switch(hass):
    """Test successful creation of switch entity."""
    data = {}
    await setup_bridge(hass, data)
    switch = Mock()
    switch.name = 'name'
    switch.type = "Smart plug"
    switch.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_light', [switch])
    await hass.async_block_till_done()
    assert "switch.name" in hass.data[deconz.DATA_DECONZ_ID]


async def test_unsupported_switch(hass):
    """Test that unsupported switches are not created."""
    await setup_bridge(hass, {"lights": UNSUPPORTED_SWITCH})
    assert len(hass.states.async_all()) == 0
