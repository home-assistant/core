"""Tests for the Freedompro lock."""
from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNLOCKED
from homeassistant.helpers import entity_registry as er


async def test_lock_get_state(hass, init_integration):
    """Test states of the lock."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "lock.lock"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNLOCKED
    assert state.attributes.get("friendly_name") == "lock"

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "2WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*2VAS3HTWINNZ5N6HVEIPDJ6NX85P2-AM-GSYWUCNPU0"
    )


async def test_lock_set_lock(hass, init_integration):
    """Test set on of the lock."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "lock.lock"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNLOCKED
    assert state.attributes.get("friendly_name") == "lock"

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "2WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*2VAS3HTWINNZ5N6HVEIPDJ6NX85P2-AM-GSYWUCNPU0"
    )

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNLOCKED


async def test_lock_set_unlock(hass, init_integration):
    """Test set on of the lock."""
    init_integration
    registry = er.async_get(hass)

    entity_id = "lock.lock"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNLOCKED
    assert state.attributes.get("friendly_name") == "lock"

    entry = registry.async_get(entity_id)
    assert entry
    assert (
        entry.unique_id
        == "2WRRJR6RCZQZSND8VP0YTO3YXCSOFPKBMW8T51TU-LQ*2VAS3HTWINNZ5N6HVEIPDJ6NX85P2-AM-GSYWUCNPU0"
    )

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNLOCKED
