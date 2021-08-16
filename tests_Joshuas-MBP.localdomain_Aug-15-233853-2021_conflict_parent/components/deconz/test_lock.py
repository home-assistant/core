"""deCONZ lock platform tests."""

from copy import deepcopy
from unittest.mock import patch

from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.components.deconz.gateway import get_gateway_from_config_entry
from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_LOCKED, STATE_UNLOCKED
from homeassistant.setup import async_setup_component

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

LOCKS = {
    "1": {
        "etag": "5c2ec06cde4bd654aef3a555fcd8ad12",
        "hascolor": False,
        "lastannounced": None,
        "lastseen": "2020-08-22T15:29:03Z",
        "manufacturername": "Danalock",
        "modelid": "V3-BTZB",
        "name": "Door lock",
        "state": {"alert": "none", "on": False, "reachable": True},
        "swversion": "19042019",
        "type": "Door Lock",
        "uniqueid": "00:00:00:00:00:00:00:00-00",
    }
}


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a gateway."""
    assert (
        await async_setup_component(
            hass, LOCK_DOMAIN, {"lock": {"platform": DECONZ_DOMAIN}}
        )
        is True
    )
    assert DECONZ_DOMAIN not in hass.data


async def test_no_locks(hass):
    """Test that no lock entities are created."""
    await setup_deconz_integration(hass)
    assert len(hass.states.async_all()) == 0


async def test_locks(hass):
    """Test that all supported lock entities are created."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["lights"] = deepcopy(LOCKS)
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    assert len(hass.states.async_all()) == 1
    assert hass.states.get("lock.door_lock").state == STATE_UNLOCKED

    door_lock = hass.states.get("lock.door_lock")
    assert door_lock.state == STATE_UNLOCKED

    state_changed_event = {
        "t": "event",
        "e": "changed",
        "r": "lights",
        "id": "1",
        "state": {"on": True},
    }
    gateway.api.event_handler(state_changed_event)
    await hass.async_block_till_done()

    assert hass.states.get("lock.door_lock").state == STATE_LOCKED

    # Verify service calls

    door_lock_device = gateway.api.lights["1"]

    # Service lock door

    with patch.object(door_lock_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: "lock.door_lock"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"on": True})

    # Service unlock door

    with patch.object(door_lock_device, "_request", return_value=True) as set_callback:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {ATTR_ENTITY_ID: "lock.door_lock"},
            blocking=True,
        )
        await hass.async_block_till_done()
        set_callback.assert_called_with("put", "/lights/1/state", json={"on": False})

    await hass.config_entries.async_unload(config_entry.entry_id)

    assert len(hass.states.async_all()) == 0
