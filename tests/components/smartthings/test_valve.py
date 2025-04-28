"""Test for the SmartThings valve platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command
from pysmartthings.models import HealthStatus
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.smartthings import MAIN
from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN, ValveState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
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

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.VALVE)


@pytest.mark.parametrize("device_fixture", ["virtual_valve"])
@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_OPEN_VALVE, Command.OPEN),
        (SERVICE_CLOSE_VALVE, Command.CLOSE),
    ],
)
async def test_valve_open_close(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    command: Command,
) -> None:
    """Test valve open and close command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        VALVE_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "valve.volvo"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "612ab3c2-3bb0-48f7-b2c0-15b169cb2fc3", Capability.VALVE, command, MAIN
    )


@pytest.mark.parametrize("device_fixture", ["virtual_valve"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("valve.volvo").state == ValveState.CLOSED

    await trigger_update(
        hass,
        devices,
        "612ab3c2-3bb0-48f7-b2c0-15b169cb2fc3",
        Capability.VALVE,
        Attribute.VALVE,
        "open",
    )

    assert hass.states.get("valve.volvo").state == ValveState.OPEN


@pytest.mark.parametrize("device_fixture", ["virtual_valve"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("valve.volvo").state == ValveState.CLOSED

    await trigger_health_update(
        hass, devices, "612ab3c2-3bb0-48f7-b2c0-15b169cb2fc3", HealthStatus.OFFLINE
    )

    assert hass.states.get("valve.volvo").state == STATE_UNAVAILABLE

    await trigger_health_update(
        hass, devices, "612ab3c2-3bb0-48f7-b2c0-15b169cb2fc3", HealthStatus.ONLINE
    )

    assert hass.states.get("valve.volvo").state == ValveState.CLOSED
