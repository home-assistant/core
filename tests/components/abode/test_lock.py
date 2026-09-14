"""Tests for the Abode lock device."""

import json
from unittest.mock import patch

from jaraco.abode.helpers import urls as URL
from requests_mock import Mocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_LOCK, SERVICE_UNLOCK
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

from tests.common import async_load_json_array_fixture, snapshot_platform

DEVICE_ID = "lock.test_lock"


async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all entities."""
    config_entry = await setup_platform(hass, LOCK_DOMAIN)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


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


async def test_retrofit_lock_discovered(
    hass: HomeAssistant, requests_mock: Mocker
) -> None:
    """Test retrofit locks are discovered as lock entities."""
    devices = await async_load_json_array_fixture(hass, "devices.json", "abode")
    for device in devices:
        if device["type_tag"] == "device_type.door_lock":
            device["type_tag"] = "device_type.retrofit_lock"
            device["type"] = "Retrofit Lock"
            break

    requests_mock.get(URL.DEVICES, text=json.dumps(devices))

    await setup_platform(hass, LOCK_DOMAIN)

    state = hass.states.get(DEVICE_ID)
    assert state is not None
    assert state.state == LockState.LOCKED
