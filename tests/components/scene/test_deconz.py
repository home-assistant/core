"""deCONZ scene platform tests."""
from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.setup import async_setup_component

import homeassistant.components.scene as scene

from tests.common import mock_coro


GROUP = {
    "1": {
        "id": "Group 1 id",
        "name": "Group 1 name",
        "state": {},
        "action": {},
        "scenes": [{
            "id": "1",
            "name": "Scene 1"
        }],
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
    """Load the deCONZ scene platform."""
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

    await hass.config_entries.async_forward_entry_setup(config_entry, 'scene')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert await async_setup_component(hass, scene.DOMAIN, {
        'scene': {
            'platform': deconz.DOMAIN
        }
    }) is True
    assert deconz.DOMAIN not in hass.data


async def test_no_scenes(hass):
    """Test that scenes can be loaded without scenes being available."""
    await setup_gateway(hass, {})
    assert len(hass.data[deconz.DOMAIN].deconz_ids) == 0
    assert len(hass.states.async_all()) == 0


async def test_scenes(hass):
    """Test that scenes works."""
    with patch('pydeconz.DeconzSession.async_put_state',
               return_value=mock_coro(True)):
        await setup_gateway(hass, {"groups": GROUP})
    assert "scene.group_1_name_scene_1" in hass.data[deconz.DOMAIN].deconz_ids
    assert len(hass.states.async_all()) == 1

    await hass.services.async_call('scene', 'turn_on', {
        'entity_id': 'scene.group_1_name_scene_1'
    }, blocking=True)


async def test_unload_scene(hass):
    """Test that it works to unload scene entities."""
    await setup_gateway(hass, {"groups": GROUP})

    await hass.data[deconz.DOMAIN].async_reset()

    assert len(hass.states.async_all()) == 0
