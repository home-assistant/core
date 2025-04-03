"""Tests for Bosch Alarm component."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import call_observable, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch("homeassistant.components.bosch_alarm.PLATFORMS", [Platform.LOCK]):
        yield


async def test_update_lock_device(
    hass: HomeAssistant,
    mock_panel: AsyncMock,
    door: AsyncMock,
    entity_id: str,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that lock stats update when locking and unlocking the door."""
    await setup_integration(hass, mock_config_entry)
    entity_id = f"lock.{entity_id}_main_door"
    assert hass.states.get(entity_id).state == LockState.LOCKED
    await hass.services.async_call(
        LOCK_DOMAIN,
        "unlock",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    door.is_locked.return_value = False
    door.is_open.return_value = True
    await call_observable(hass, door.status_observer)
    assert hass.states.get(entity_id).state == LockState.UNLOCKED
    await hass.services.async_call(
        LOCK_DOMAIN,
        "lock",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    door.is_locked.return_value = True
    door.is_open.return_value = False
    await call_observable(hass, door.status_observer)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == LockState.LOCKED


async def test_lock(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_panel: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the lock state."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
