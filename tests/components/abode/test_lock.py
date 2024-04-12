"""Tests for the Abode lock device."""

from unittest.mock import patch

from homeassistant.components.abode import ATTR_DEVICE_ID
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    STATE_LOCKED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

DEVICE_ID = "lock.test_lock"


async def test_entity_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, LOCK_DOMAIN)

    entry = entity_registry.async_get(DEVICE_ID)
    assert entry.unique_id == "51cab3b545d2o34ed7fz02731bda5324"


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the lock attributes are correct."""
    await setup_platform(hass, LOCK_DOMAIN)

    state = hass.states.get(DEVICE_ID)
    assert state.state == STATE_LOCKED
    assert state.attributes.get(ATTR_DEVICE_ID) == "ZW:00000004"
    assert not state.attributes.get("battery_low")
    assert not state.attributes.get("no_response")
    assert state.attributes.get("device_type") == "Door Lock"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Test Lock"


async def test_lock(hass: HomeAssistant) -> None:
    """Test the lock can be locked."""
    await setup_platform(hass, LOCK_DOMAIN)

    with patch("jaraco.abode.devices.lock.Lock.lock") as mock_lock:
        await hass.services.async_call(
            LOCK_DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
        )
        await hass.async_block_till_done()
        mock_lock.assert_called_once()


async def test_unlock(hass: HomeAssistant) -> None:
    """Test the lock can be unlocked."""
    await setup_platform(hass, LOCK_DOMAIN)

    with patch("jaraco.abode.devices.lock.Lock.unlock") as mock_unlock:
        await hass.services.async_call(
            LOCK_DOMAIN, SERVICE_UNLOCK, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
        )
        await hass.async_block_till_done()
        mock_unlock.assert_called_once()
