"""Tests for the Glutz eAccess lock platform."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from pyglutz_eaccess import GlutzAuthError, GlutzConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.glutz_eaccess.const import DOMAIN
from homeassistant.components.glutz_eaccess.coordinator import SCAN_INTERVAL
from homeassistant.components.glutz_eaccess.lock import UNLOCK_DURATION
from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    LockState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_AP1 = "lock.main_door"
ENTITY_AP2 = "lock.door_ap_2"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_glutz_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all lock entities match snapshot."""
    with patch("homeassistant.components.glutz_eaccess.PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_initial_state_locked(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that locks start in the locked state."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_AP1).state == LockState.LOCKED
    assert hass.states.get(ENTITY_AP2).state == LockState.LOCKED


async def test_device_name_from_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that device name uses the last location component."""
    await setup_integration(hass, mock_config_entry)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, "ap-1")})
    assert device is not None
    assert device.name == "Main Door"


async def test_device_name_fallback_no_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test fallback device name when location list is empty."""
    await setup_integration(hass, mock_config_entry)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, "ap-2")})
    assert device is not None
    assert device.name == "Door ap-2"


async def test_unlock_sets_state_unlocked(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that calling unlock changes state to unlocked."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: ENTITY_AP1},
        blocking=True,
    )

    assert hass.states.get(ENTITY_AP1).state == LockState.UNLOCKED
    mock_glutz_client.open_access_point.assert_called_once_with("ap-1")


async def test_unlock_auto_relocks_after_duration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
    freezer,
) -> None:
    """Test that the door auto-relocks after UNLOCK_DURATION seconds."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: ENTITY_AP1},
        blocking=True,
    )
    assert hass.states.get(ENTITY_AP1).state == LockState.UNLOCKED

    freezer.tick(timedelta(seconds=UNLOCK_DURATION + 1))
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_AP1).state == LockState.LOCKED


async def test_open_sets_state_unlocked_and_cancels_relock(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
    freezer,
) -> None:
    """Test that open (hold) cancels any pending relock and sets unlocked."""
    await setup_integration(hass, mock_config_entry)

    # First unlock (schedules relock)
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: ENTITY_AP1},
        blocking=True,
    )

    # Then hold open — relock should be cancelled
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_OPEN,
        {ATTR_ENTITY_ID: ENTITY_AP1},
        blocking=True,
    )

    freezer.tick(timedelta(seconds=UNLOCK_DURATION + 1))
    await hass.async_block_till_done()

    # Relock task was cancelled; door stays unlocked
    assert hass.states.get(ENTITY_AP1).state == LockState.UNLOCKED
    mock_glutz_client.hold_open_access_point.assert_called_once_with("ap-1")


async def test_lock_service_sets_state_locked(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that calling lock after unlock sets state back to locked."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: ENTITY_AP1},
        blocking=True,
    )
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: ENTITY_AP1},
        blocking=True,
    )

    assert hass.states.get(ENTITY_AP1).state == LockState.LOCKED
    mock_glutz_client.close_access_point.assert_called_once_with("ap-1")


async def test_unlocked_state_preserved_across_coordinator_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that a coordinator refresh does not reset a held-open door to locked."""
    await setup_integration(hass, mock_config_entry)

    # SERVICE_OPEN (hold) sets unlocked without scheduling a relock task,
    # so the coordinator refresh has no competing task.
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_OPEN,
        {ATTR_ENTITY_ID: ENTITY_AP1},
        blocking=True,
    )
    assert hass.states.get(ENTITY_AP1).state == LockState.UNLOCKED

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Coordinator push must not reset our optimistic unlocked state
    assert hass.states.get(ENTITY_AP1).state == LockState.UNLOCKED


@pytest.mark.parametrize(
    ("service", "api_method"),
    [
        (SERVICE_UNLOCK, "open_access_point"),
        (SERVICE_LOCK, "close_access_point"),
        (SERVICE_OPEN, "hold_open_access_point"),
    ],
)
async def test_service_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
    service: str,
    api_method: str,
) -> None:
    """Test that GlutzAuthError during service call triggers reauth and raises."""
    await setup_integration(hass, mock_config_entry)

    getattr(mock_glutz_client, api_method).side_effect = GlutzAuthError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LOCK_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_AP1},
            blocking=True,
        )

    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


@pytest.mark.parametrize(
    ("service", "api_method"),
    [
        (SERVICE_UNLOCK, "open_access_point"),
        (SERVICE_LOCK, "close_access_point"),
        (SERVICE_OPEN, "hold_open_access_point"),
    ],
)
async def test_service_connection_error_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
    service: str,
    api_method: str,
) -> None:
    """Test that GlutzConnectionError during service call raises HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    getattr(mock_glutz_client, api_method).side_effect = GlutzConnectionError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LOCK_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_AP1},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "api_method"),
    [
        (SERVICE_UNLOCK, "open_access_point"),
        (SERVICE_LOCK, "close_access_point"),
        (SERVICE_OPEN, "hold_open_access_point"),
    ],
)
async def test_service_api_returns_false_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
    service: str,
    api_method: str,
) -> None:
    """Test that False return from API raises HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    getattr(mock_glutz_client, api_method).return_value = False

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LOCK_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_AP1},
            blocking=True,
        )


async def test_entity_unavailable_when_access_point_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
    freezer,
) -> None:
    """Test entity becomes unavailable when its AP is removed from coordinator data."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_AP1).state == LockState.LOCKED

    # Simulate the API returning only ap-2 (ap-1 removed)
    mock_glutz_client.get_access_points.return_value = [
        {"accessPointId": "ap-2", "location": []}
    ]

    freezer.tick(SCAN_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_AP1).state == STATE_UNAVAILABLE


async def test_unlock_twice_cancels_first_relock(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
    freezer,
) -> None:
    """Test that a second unlock cancels the pending relock from the first."""
    await setup_integration(hass, mock_config_entry)

    # First unlock — schedules relock task
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: ENTITY_AP1},
        blocking=True,
    )
    assert hass.states.get(ENTITY_AP1).state == LockState.UNLOCKED

    # Second unlock — must cancel the first relock and schedule a new one
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: ENTITY_AP1},
        blocking=True,
    )
    assert hass.states.get(ENTITY_AP1).state == LockState.UNLOCKED

    # After the relock duration the door should lock (new relock task is active)
    freezer.tick(timedelta(seconds=UNLOCK_DURATION + 1))
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_AP1).state == LockState.LOCKED
