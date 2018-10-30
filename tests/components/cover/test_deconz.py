"""deCONZ cover platform tests."""
from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components import deconz
from homeassistant.components.deconz.const import COVER_TYPES
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

import homeassistant.components.cover as cover

from tests.common import mock_coro

SUPPORTED_COVERS = {
    "1": {
        "id": "Cover 1 id",
        "name": "Cover 1 name",
        "type": "Level controllable output",
        "state": {"bri": 255, "reachable": True},
        "modelid": "Not zigbee spec",
        "uniqueid": "00:00:00:00:00:00:00:00-00"
    },
    "2": {
        "id": "Cover 2 id",
        "name": "Cover 2 name",
        "type": "Window covering device",
        "state": {"bri": 255, "reachable": True},
        "modelid": "lumi.curtain"
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


ENTRY_CONFIG = {
    deconz.const.CONF_ALLOW_CLIP_SENSOR: True,
    deconz.const.CONF_ALLOW_DECONZ_GROUPS: True,
    deconz.config_flow.CONF_API_KEY: "ABCDEF",
    deconz.config_flow.CONF_BRIDGEID: "0123456789",
    deconz.config_flow.CONF_HOST: "1.2.3.4",
    deconz.config_flow.CONF_PORT: 80
}


async def setup_gateway(hass, data):
    """Load the deCONZ cover platform."""
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

    await hass.config_entries.async_forward_entry_setup(config_entry, 'cover')
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert await async_setup_component(hass, cover.DOMAIN, {
        'cover': {
            'platform': deconz.DOMAIN
        }
    }) is True
    assert deconz.DOMAIN not in hass.data


async def test_no_covers(hass):
    """Test that no cover entities are created."""
    await setup_gateway(hass, {})
    assert len(hass.data[deconz.DOMAIN].deconz_ids) == 0
    assert len(hass.states.async_all()) == 0


async def test_cover(hass):
    """Test that all supported cover entities are created."""
    with patch('pydeconz.DeconzSession.async_put_state',
               return_value=mock_coro(True)):
        await setup_gateway(hass, {"lights": SUPPORTED_COVERS})
    assert "cover.cover_1_name" in hass.data[deconz.DOMAIN].deconz_ids
    assert len(SUPPORTED_COVERS) == len(COVER_TYPES)
    assert len(hass.states.async_all()) == 3

    cover_1 = hass.states.get('cover.cover_1_name')
    assert cover_1 is not None
    assert cover_1.state == 'closed'

    hass.data[deconz.DOMAIN].api.lights['1'].async_update({})

    await hass.services.async_call('cover', 'open_cover', {
        'entity_id': 'cover.cover_1_name'
    }, blocking=True)
    await hass.services.async_call('cover', 'close_cover', {
        'entity_id': 'cover.cover_1_name'
    }, blocking=True)
    await hass.services.async_call('cover', 'stop_cover', {
        'entity_id': 'cover.cover_1_name'
    }, blocking=True)

    await hass.services.async_call('cover', 'close_cover', {
        'entity_id': 'cover.cover_2_name'
    }, blocking=True)


async def test_add_new_cover(hass):
    """Test successful creation of cover entity."""
    data = {}
    await setup_gateway(hass, data)
    cover = Mock()
    cover.name = 'name'
    cover.type = "Level controllable output"
    cover.register_async_callback = Mock()
    async_dispatcher_send(hass, 'deconz_new_light', [cover])
    await hass.async_block_till_done()
    assert "cover.name" in hass.data[deconz.DOMAIN].deconz_ids


async def test_unsupported_cover(hass):
    """Test that unsupported covers are not created."""
    await setup_gateway(hass, {"lights": UNSUPPORTED_COVER})
    assert len(hass.states.async_all()) == 0


async def test_unload_cover(hass):
    """Test that it works to unload switch entities."""
    await setup_gateway(hass, {"lights": SUPPORTED_COVERS})

    await hass.data[deconz.DOMAIN].async_reset()

    assert len(hass.states.async_all()) == 1
