"""Tests for Xthings Cloud lock platform."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    LockState,
)
from homeassistant.components.xthings_cloud.const import DEFAULT_SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_device_by_id, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_locks(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test lock entities are created correctly."""
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_LOCK, "async_lock_lock"),
        (SERVICE_UNLOCK, "async_lock_unlock"),
    ],
)
async def test_lock_lock_unlock(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    service: str,
    method: str,
) -> None:
    """Test locking and unlocking a lock."""
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LOCK_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "lock.front_door_lock"},
        blocking=True,
    )
    getattr(mock_api_client, method).assert_called_once_with("dev_lock_001")


async def test_lock_unavailable_when_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test lock shows unavailable when device is offline."""
    get_device_by_id(mock_api_client, "dev_lock_001")["online"] = False
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("lock.front_door_lock")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_updating_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    mock_websocket: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test updating state."""
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("lock.front_door_lock")
    assert state is not None
    assert state.state == LockState.LOCKED.value

    polling_response = deepcopy(mock_api_client.async_get_devices.return_value)
    mock_api_client.async_get_devices.side_effect = [
        deepcopy(polling_response),
        deepcopy(polling_response),
    ]
    mock_websocket.call_args[1]["on_device_status"](
        "dev_lock_001",
        {
            "is_locked": 1,
            "jammed": False,
            "battery": 80,
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("lock.front_door_lock")
    assert state is not None
    assert state.state == LockState.UNLOCKED.value

    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_api_client.async_get_devices.await_count == 2

    state = hass.states.get("lock.front_door_lock")
    assert state is not None
    assert state.state == LockState.UNLOCKED.value

    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_api_client.async_get_devices.await_count == 3

    state = hass.states.get("lock.front_door_lock")
    assert state is not None
    assert state.state == LockState.LOCKED.value


async def test_legacy_locked_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test the legacy locked state field."""
    status = get_device_by_id(mock_api_client, "dev_lock_001")["status"]
    status.pop("is_locked")
    status["locked"] = True

    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("lock.front_door_lock")
    assert state is not None
    assert state.state == LockState.LOCKED.value
