"""deCONZ lock platform tests."""

from copy import deepcopy

from homeassistant.components.deconz.gateway import get_gateway_from_config_entry
from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_LOCKED,
    STATE_UNAVAILABLE,
    STATE_UNLOCKED,
)

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    setup_deconz_integration,
)

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


async def test_no_locks(hass, aioclient_mock):
    """Test that no lock entities are created."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


async def test_locks(hass, aioclient_mock):
    """Test that all supported lock entities are created."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["lights"] = deepcopy(LOCKS)
    config_entry = await setup_deconz_integration(
        hass, aioclient_mock, get_state_response=data
    )
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

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/lights/1/state")

    # Service lock door

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.door_lock"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"on": True}

    # Service unlock door

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: "lock.door_lock"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"on": False}

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    assert len(hass.states.async_all()) == 1
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
