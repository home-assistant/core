"""deCONZ cover platform tests."""

from copy import deepcopy
from unittest.mock import patch

from homeassistant.components.cover import (
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
)
from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.components.deconz.gateway import get_gateway_from_config_entry
from homeassistant.const import ATTR_ENTITY_ID, STATE_CLOSED, STATE_OPEN
from homeassistant.setup import async_setup_component

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

COVERS = {
    "1": {
        "id": "Level controllable cover id",
        "name": "Level controllable cover",
        "type": "Level controllable output",
        "state": {"bri": 254, "on": False, "reachable": True},
        "modelid": "Not zigbee spec",
        "uniqueid": "00:00:00:00:00:00:00:00-00",
    },
    "2": {
        "id": "Window covering device id",
        "name": "Window covering device",
        "type": "Window covering device",
        "state": {"lift": 100, "open": False, "reachable": True},
        "modelid": "lumi.curtain",
        "uniqueid": "00:00:00:00:00:00:00:01-00",
    },
    "3": {
        "id": "Unsupported cover id",
        "name": "Unsupported cover",
        "type": "Not a cover",
        "state": {"reachable": True},
        "uniqueid": "00:00:00:00:00:00:00:02-00",
    },
    "4": {
        "id": "deconz old brightness cover id",
        "name": "deconz old brightness cover",
        "type": "Level controllable output",
        "state": {"bri": 255, "on": False, "reachable": True},
        "modelid": "Not zigbee spec",
        "uniqueid": "00:00:00:00:00:00:00:03-00",
    },
    "5": {
        "id": "Window covering controller id",
        "name": "Window covering controller",
        "type": "Window covering controller",
        "state": {"bri": 253, "on": True, "reachable": True},
        "modelid": "Motor controller",
        "uniqueid": "00:00:00:00:00:00:00:04-00",
    },
}


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert (
        await async_setup_component(
            hass, COVER_DOMAIN, {"cover": {"platform": DECONZ_DOMAIN}}
        )
        is True
    )
    assert DECONZ_DOMAIN not in hass.data


async def test_no_covers(hass):
    """Test that no cover entities are created."""
    await setup_deconz_integration(hass)
    assert len(hass.states.async_all()) == 0


async def test_cover(hass):
    """Test that all supported cover entities are created."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["lights"] = deepcopy(COVERS)
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 5
    assert hass.states.get("cover.level_controllable_cover").state == STATE_OPEN
    assert hass.states.get("cover.window_covering_device").state == STATE_CLOSED
    assert hass.states.get("cover.unsupported_cover") is None
    assert hass.states.get("cover.deconz_old_brightness_cover").state == STATE_OPEN
    assert hass.states.get("cover.window_covering_controller").state == STATE_CLOSED

    # Event signals cover is closed

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "lights",
        "id": "1",
        "state": {"on": True},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("cover.level_controllable_cover").state == STATE_CLOSED

    # Verify service calls for cover

    windows_covering_device = gateway.api.lights["2"]

    # Service open cover

    with patch.object(
        windows_covering_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: "cover.window_covering_device"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/2/state", json={"open": True})

    # Service close cover

    with patch.object(
        windows_covering_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: "cover.window_covering_device"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/2/state", json={"open": False})

    # Service set cover position

    with patch.object(
        windows_covering_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: "cover.window_covering_device", ATTR_POSITION: 40},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/2/state", json={"lift": 60})

    # Service stop cover movement

    with patch.object(
        windows_covering_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: "cover.window_covering_device"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/2/state", json={"stop": True})

    # Verify service calls for legacy cover

    level_controllable_cover_device = gateway.api.lights["1"]

    # Service open cover

    with patch.object(
        level_controllable_cover_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: "cover.level_controllable_cover"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"on": False})

    # Service close cover

    with patch.object(
        level_controllable_cover_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: "cover.level_controllable_cover"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"on": True})

    # Service set cover position

    with patch.object(
        level_controllable_cover_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: "cover.level_controllable_cover", ATTR_POSITION: 40},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"bri": 152})

    # Service stop cover movement

    with patch.object(
        level_controllable_cover_device, "_request", return_value=True
    ) as set_callback:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: "cover.level_controllable_cover"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"bri_inc": 0})

    # Test that a reported cover position of 255 (deconz-rest-api < 2.05.73) is interpreted correctly.
    assert hass.states.get("cover.deconz_old_brightness_cover").state == STATE_OPEN

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "lights",
        "id": "4",
        "state": {"on": True},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    deconz_old_brightness_cover = hass.states.get("cover.deconz_old_brightness_cover")
    assert deconz_old_brightness_cover.state == STATE_CLOSED
    assert deconz_old_brightness_cover.attributes["current_position"] == 0

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert len(hass.states.async_all()) == 0


async def test_tilt_cover(hass):
    """Test that tilting a cover works."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["lights"] = {
        "0": {
            "etag": "87269755b9b3a046485fdae8d96b252c",
            "lastannounced": None,
            "lastseen": "2020-08-01T16:22:05Z",
            "manufacturername": "AXIS",
            "modelid": "Gear",
            "name": "Covering device",
            "state": {
                "bri": 0,
                "lift": 0,
                "on": False,
                "open": True,
                "reachable": True,
                "tilt": 0,
            },
            "swversion": "100-5.3.5.1122",
            "type": "Window covering device",
            "uniqueid": "00:24:46:00:00:12:34:56-01",
        }
    }
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 1
    entity = hass.states.get("cover.covering_device")
    assert entity.state == STATE_OPEN
    assert entity.attributes[ATTR_CURRENT_TILT_POSITION] == 100

    covering_device = gateway.api.lights["0"]

    with patch.object(covering_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            {ATTR_ENTITY_ID: "cover.covering_device", ATTR_TILT_POSITION: 40},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/0/state", json={"tilt": 60})

    with patch.object(covering_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: "cover.covering_device"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/0/state", json={"tilt": 0})

    with patch.object(covering_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: "cover.covering_device"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/0/state", json={"tilt": 100})

    # Service stop cover movement

    with patch.object(covering_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER_TILT,
            {ATTR_ENTITY_ID: "cover.covering_device"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/0/state", json={"stop": True})
