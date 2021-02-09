"""Tests for the Freedompro lock."""
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, SERVICE_LOCK
from homeassistant.const import ATTR_ENTITY_ID, STATE_LOCKED, STATE_UNLOCKED

from tests.components.freedompro import init_integration


async def test_lock_get_state(hass):
    """Test states of the lock."""
    await init_integration(hass)
    registry = await hass.helpers.entity_registry.async_get_registry()

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


async def test_lock_set_on(hass):
    """Test set on of the lock."""
    await init_integration(hass)
    registry = await hass.helpers.entity_registry.async_get_registry()

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
    assert state.state == STATE_LOCKED
