"""The lock tests for the Mazda Connected Services integration."""
from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    STATE_LOCKED,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration


async def test_lock_setup(hass: HomeAssistant) -> None:
    """Test locking and unlocking the vehicle."""
    await init_integration(hass)

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("lock.my_mazda3_lock")
    assert entry
    assert entry.unique_id == "JM000000000000000"

    state = hass.states.get("lock.my_mazda3_lock")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "My Mazda3 Lock"

    assert state.state == STATE_LOCKED


async def test_locking(hass: HomeAssistant) -> None:
    """Test locking the vehicle."""
    client_mock = await init_integration(hass)

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.my_mazda3_lock"},
        blocking=True,
    )
    await hass.async_block_till_done()

    client_mock.lock_doors.assert_called_once()


async def test_unlocking(hass: HomeAssistant) -> None:
    """Test unlocking the vehicle."""
    client_mock = await init_integration(hass)

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: "lock.my_mazda3_lock"},
        blocking=True,
    )
    await hass.async_block_till_done()

    client_mock.unlock_doors.assert_called_once()
