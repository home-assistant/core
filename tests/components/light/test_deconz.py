"""deCONZ light platform tests."""
from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import mock_coro


LIGHT = {
    "1": {
        "id": "Light 1 id",
        "name": "Light 1 name",
        "state": {}
    }
}

GROUP = {
    "1": {
        "id": "Group 1 id",
        "name": "Group 1 name",
        "state": {},
        "action": {},
        "scenes": [],
        "lights": [
            "1",
            "2"
        ]
    },
    "2": {
        "id": "Group 2 id",
        "name": "Group 2 name",
        "state": {},
        "action": {},
        "scenes": []
    },
}

SWITCH = {
    "1": {
        "id": "Switch 1 id",
        "name": "Switch 1 name",
        "type": "On/Off plug-in unit",
        "state": {}
    }
}


async def setup_bridge(hass, data, allow_deconz_groups=True):
    """Load the deCONZ light platform."""
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
        1, deconz.DOMAIN, 'Mock Title',
        {'host': 'mock-host', 'allow_deconz_groups': allow_deconz_groups},
        'test', config_entries.CONN_CLASS_LOCAL_PUSH)
    await hass.config_entries.async_forward_entry_setup(config_entry, 'light')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_no_lights_or_groups(hass):
    """Test that no lights or groups entities are created."""
    data = {}
    await setup_bridge(hass, data)
    assert len(hass.data[deconz.DATA_DECONZ_ID]) == 0
    assert len(hass.states.async_all()) == 0


async def test_lights_and_groups(hass):
    """Test that lights or groups entities are created."""
    await setup_bridge(hass, {"lights": LIGHT, "groups": GROUP})
    assert "light.light_1_name" in hass.data[deconz.DATA_DECONZ_ID]
    assert "light.group_1_name" in hass.data[deconz.DATA_DECONZ_ID]
    assert "light.group_2_name" not in hass.data[deconz.DATA_DECONZ_ID]
    assert len(hass.states.async_all()) == 3


async def test_add_new_light(hass):
    """Test successful creation of light entities."""
    data = {}
    await setup_bridge(hass, data)
    light = Mock()
    light.name = 'name'
    light.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_light', [light])
    await hass.async_block_till_done()
    assert "light.name" in hass.data[deconz.DATA_DECONZ_ID]


async def test_add_new_group(hass):
    """Test successful creation of group entities."""
    data = {}
    await setup_bridge(hass, data)
    group = Mock()
    group.name = 'name'
    group.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_group', [group])
    await hass.async_block_till_done()
    assert "light.name" in hass.data[deconz.DATA_DECONZ_ID]


async def test_do_not_add_deconz_groups(hass):
    """Test that clip sensors can be ignored."""
    data = {}
    await setup_bridge(hass, data, allow_deconz_groups=False)
    group = Mock()
    group.name = 'name'
    group.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_group', [group])
    await hass.async_block_till_done()
    assert len(hass.data[deconz.DATA_DECONZ_ID]) == 0


async def test_no_switch(hass):
    """Test that a switch doesn't get created as a light entity."""
    await setup_bridge(hass, {"lights": SWITCH})
    assert len(hass.data[deconz.DATA_DECONZ_ID]) == 0
    assert len(hass.states.async_all()) == 0
