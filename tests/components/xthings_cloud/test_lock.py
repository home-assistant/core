"""Tests for Xthings Cloud lock platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_device_by_id, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


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
) -> None:
    """Test updating state."""
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("lock.front_door_lock")
    assert state is not None
    assert state.state == "locked"

    mock_websocket.call_args[1]["on_device_status"](
        "dev_lock_001",
        {
            "locked": False,
            "jammed": False,
            "battery": 80,
        },
    )

    state = hass.states.get("lock.front_door_lock")
    assert state is not None
    assert state.state == "unlocked"
