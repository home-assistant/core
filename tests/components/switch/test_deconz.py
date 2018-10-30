"""deCONZ switch platform tests."""
from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.components.deconz.const import SWITCH_TYPES
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

import homeassistant.components.switch as switch

from tests.common import mock_coro

SUPPORTED_SWITCHES = {
    "1": {
        "id": "Switch 1 id",
        "name": "Switch 1 name",
        "type": "On/Off plug-in unit",
        "state": {"on": True, "reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:00-00"
    },
    "2": {
        "id": "Switch 2 id",
        "name": "Switch 2 name",
        "type": "Smart plug",
        "state": {"on": True, "reachable": True}
    },
    "3": {
        "id": "Switch 3 id",
        "name": "Switch 3 name",
        "type": "Warning device",
        "state": {"alert": "lselect", "reachable": True}
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


ENTRY_CONFIG = {
    deconz.const.CONF_ALLOW_CLIP_SENSOR: True,
    deconz.const.CONF_ALLOW_DECONZ_GROUPS: True,
    deconz.config_flow.CONF_API_KEY: "ABCDEF",
    deconz.config_flow.CONF_BRIDGEID: "0123456789",
    deconz.config_flow.CONF_HOST: "1.2.3.4",
    deconz.config_flow.CONF_PORT: 80
}


async def setup_gateway(hass, data):
    """Load the deCONZ switch platform."""
    from pydeconz import DeconzSession
    loop = Mock()
    session = Mock()

    config_entry = config_entries.ConfigEntry(
        1, deconz.DOMAIN, 'Mock Title', ENTRY_CONFIG, 'test',
        config_entries.CONN_CLASS_LOCAL_PUSH)
    gateway = deconz.DeconzGateway(hass, config_entry)
    gateway.api = DeconzSession(loop, session, **config_entry.data)
    gateway.api.config = Mock()
    hass.data[deconz.DOMAIN] = gateway

    with patch('pydeconz.DeconzSession.async_get_state',
               return_value=mock_coro(data)):
        await gateway.api.async_load_parameters()

    await hass.config_entries.async_forward_entry_setup(config_entry, 'switch')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert await async_setup_component(hass, switch.DOMAIN, {
        'switch': {
            'platform': deconz.DOMAIN
        }
    }) is True
    assert deconz.DOMAIN not in hass.data


async def test_no_switches(hass):
    """Test that no switch entities are created."""
    await setup_gateway(hass, {})
    assert len(hass.data[deconz.DOMAIN].deconz_ids) == 0
    assert len(hass.states.async_all()) == 0


async def test_switches(hass):
    """Test that all supported switch entities are created."""
    with patch('pydeconz.DeconzSession.async_put_state',
               return_value=mock_coro(True)):
        await setup_gateway(hass, {"lights": SUPPORTED_SWITCHES})
    assert "switch.switch_1_name" in hass.data[deconz.DOMAIN].deconz_ids
    assert "switch.switch_2_name" in hass.data[deconz.DOMAIN].deconz_ids
    assert "switch.switch_3_name" in hass.data[deconz.DOMAIN].deconz_ids
    assert len(SUPPORTED_SWITCHES) == len(SWITCH_TYPES)
    assert len(hass.states.async_all()) == 4

    switch_1 = hass.states.get('switch.switch_1_name')
    assert switch_1 is not None
    assert switch_1.state == 'on'
    switch_3 = hass.states.get('switch.switch_3_name')
    assert switch_3 is not None
    assert switch_3.state == 'on'

    hass.data[deconz.DOMAIN].api.lights['1'].async_update({})

    await hass.services.async_call('switch', 'turn_on', {
        'entity_id': 'switch.switch_1_name'
    }, blocking=True)
    await hass.services.async_call('switch', 'turn_off', {
        'entity_id': 'switch.switch_1_name'
    }, blocking=True)

    await hass.services.async_call('switch', 'turn_on', {
        'entity_id': 'switch.switch_3_name'
    }, blocking=True)
    await hass.services.async_call('switch', 'turn_off', {
        'entity_id': 'switch.switch_3_name'
    }, blocking=True)


async def test_add_new_switch(hass):
    """Test successful creation of switch entity."""
    await setup_gateway(hass, {})
    switch = Mock()
    switch.name = 'name'
    switch.type = "Smart plug"
    switch.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_light', [switch])
    await hass.async_block_till_done()
    assert "switch.name" in hass.data[deconz.DOMAIN].deconz_ids


async def test_unsupported_switch(hass):
    """Test that unsupported switches are not created."""
    await setup_gateway(hass, {"lights": UNSUPPORTED_SWITCH})
    assert len(hass.states.async_all()) == 0


async def test_unload_switch(hass):
    """Test that it works to unload switch entities."""
    await setup_gateway(hass, {"lights": SUPPORTED_SWITCHES})

    await hass.data[deconz.DOMAIN].async_reset()

    assert len(hass.states.async_all()) == 1
