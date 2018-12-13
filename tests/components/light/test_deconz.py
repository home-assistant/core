"""deCONZ light platform tests."""
from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

import homeassistant.components.light as light

from tests.common import mock_coro


LIGHT = {
    "1": {
        "id": "Light 1 id",
        "name": "Light 1 name",
        "state": {
            "on": True, "bri": 255, "colormode": "xy", "xy": (500, 500),
            "reachable": True
        },
        "uniqueid": "00:00:00:00:00:00:00:00-00"
    },
    "2": {
        "id": "Light 2 id",
        "name": "Light 2 name",
        "state": {
            "on": True, "colormode": "ct", "ct": 2500, "reachable": True
        }
    }
}

GROUP = {
    "1": {
        "id": "Group 1 id",
        "name": "Group 1 name",
        "type": "LightGroup",
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


ENTRY_CONFIG = {
    deconz.const.CONF_ALLOW_CLIP_SENSOR: True,
    deconz.const.CONF_ALLOW_DECONZ_GROUPS: True,
    deconz.config_flow.CONF_API_KEY: "ABCDEF",
    deconz.config_flow.CONF_BRIDGEID: "0123456789",
    deconz.config_flow.CONF_HOST: "1.2.3.4",
    deconz.config_flow.CONF_PORT: 80
}


async def setup_gateway(hass, data, allow_deconz_groups=True):
    """Load the deCONZ light platform."""
    from pydeconz import DeconzSession
    loop = Mock()
    session = Mock()

    ENTRY_CONFIG[deconz.const.CONF_ALLOW_DECONZ_GROUPS] = allow_deconz_groups

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

    await hass.config_entries.async_forward_entry_setup(config_entry, 'light')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert await async_setup_component(hass, light.DOMAIN, {
        'light': {
            'platform': deconz.DOMAIN
        }
    }) is True
    assert deconz.DOMAIN not in hass.data


async def test_no_lights_or_groups(hass):
    """Test that no lights or groups entities are created."""
    await setup_gateway(hass, {})
    assert len(hass.data[deconz.DOMAIN].deconz_ids) == 0
    assert len(hass.states.async_all()) == 0


async def test_lights_and_groups(hass):
    """Test that lights or groups entities are created."""
    with patch('pydeconz.DeconzSession.async_put_state',
               return_value=mock_coro(True)):
        await setup_gateway(hass, {"lights": LIGHT, "groups": GROUP})
    assert "light.light_1_name" in hass.data[deconz.DOMAIN].deconz_ids
    assert "light.light_2_name" in hass.data[deconz.DOMAIN].deconz_ids
    assert "light.group_1_name" in hass.data[deconz.DOMAIN].deconz_ids
    assert "light.group_2_name" not in hass.data[deconz.DOMAIN].deconz_ids
    assert len(hass.states.async_all()) == 4

    lamp_1 = hass.states.get('light.light_1_name')
    assert lamp_1 is not None
    assert lamp_1.state == 'on'
    assert lamp_1.attributes['brightness'] == 255
    assert lamp_1.attributes['hs_color'] == (224.235, 100.0)

    light_2 = hass.states.get('light.light_2_name')
    assert light_2 is not None
    assert light_2.state == 'on'
    assert light_2.attributes['color_temp'] == 2500

    hass.data[deconz.DOMAIN].api.lights['1'].async_update({})

    await hass.services.async_call('light', 'turn_on', {
        'entity_id': 'light.light_1_name',
        'color_temp': 2500,
        'brightness': 200,
        'transition': 5,
        'flash': 'short',
        'effect': 'colorloop'
    }, blocking=True)
    await hass.services.async_call('light', 'turn_on', {
        'entity_id': 'light.light_1_name',
        'hs_color': (20, 30),
        'flash': 'long',
        'effect': 'None'
    }, blocking=True)
    await hass.services.async_call('light', 'turn_off', {
        'entity_id': 'light.light_1_name',
        'transition': 5,
        'flash': 'short'
    }, blocking=True)
    await hass.services.async_call('light', 'turn_off', {
        'entity_id': 'light.light_1_name',
        'flash': 'long'
    }, blocking=True)


async def test_add_new_light(hass):
    """Test successful creation of light entities."""
    await setup_gateway(hass, {})
    light = Mock()
    light.name = 'name'
    light.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_light', [light])
    await hass.async_block_till_done()
    assert "light.name" in hass.data[deconz.DOMAIN].deconz_ids


async def test_add_new_group(hass):
    """Test successful creation of group entities."""
    await setup_gateway(hass, {})
    group = Mock()
    group.name = 'name'
    group.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_group', [group])
    await hass.async_block_till_done()
    assert "light.name" in hass.data[deconz.DOMAIN].deconz_ids


async def test_do_not_add_deconz_groups(hass):
    """Test that clip sensors can be ignored."""
    await setup_gateway(hass, {}, allow_deconz_groups=False)
    group = Mock()
    group.name = 'name'
    group.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_group', [group])
    await hass.async_block_till_done()
    assert len(hass.data[deconz.DOMAIN].deconz_ids) == 0


async def test_no_switch(hass):
    """Test that a switch doesn't get created as a light entity."""
    await setup_gateway(hass, {"lights": SWITCH})
    assert len(hass.data[deconz.DOMAIN].deconz_ids) == 0
    assert len(hass.states.async_all()) == 0


async def test_unload_light(hass):
    """Test that it works to unload switch entities."""
    await setup_gateway(hass, {"lights": LIGHT, "groups": GROUP})

    await hass.data[deconz.DOMAIN].async_reset()

    # Group.all_lights will not be removed
    assert len(hass.states.async_all()) == 1
