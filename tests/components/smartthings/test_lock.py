"""Test for the SmartThings lock platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command
from pysmartthings.models import HealthStatus
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.components.smartthings.const import MAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    setup_integration,
    snapshot_smartthings_entities,
    trigger_health_update,
    trigger_update,
)

from tests.common import MockConfigEntry


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.LOCK)


@pytest.mark.parametrize("device_fixture", ["yale_push_button_deadbolt_lock"])
@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_LOCK, Command.LOCK),
        (SERVICE_UNLOCK, Command.UNLOCK),
    ],
)
async def test_lock_unlock(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    command: Command,
) -> None:
    """Test lock and unlock command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LOCK_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "lock.basement_door_lock"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "a9f587c5-5d8b-4273-8907-e7f609af5158",
        Capability.LOCK,
        command,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["yale_push_button_deadbolt_lock"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("lock.basement_door_lock").state == LockState.LOCKED

    await trigger_update(
        hass,
        devices,
        "a9f587c5-5d8b-4273-8907-e7f609af5158",
        Capability.LOCK,
        Attribute.LOCK,
        "open",
    )

    assert hass.states.get("lock.basement_door_lock").state == LockState.UNLOCKED


@pytest.mark.parametrize("device_fixture", ["yale_push_button_deadbolt_lock"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("lock.basement_door_lock").state == LockState.LOCKED

    await trigger_health_update(
        hass, devices, "a9f587c5-5d8b-4273-8907-e7f609af5158", HealthStatus.OFFLINE
    )

    assert hass.states.get("lock.basement_door_lock").state == STATE_UNAVAILABLE

    await trigger_health_update(
        hass, devices, "a9f587c5-5d8b-4273-8907-e7f609af5158", HealthStatus.ONLINE
    )

    assert hass.states.get("lock.basement_door_lock").state == LockState.LOCKED


@pytest.mark.parametrize("device_fixture", ["yale_push_button_deadbolt_lock"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("lock.basement_door_lock").state == STATE_UNAVAILABLE
