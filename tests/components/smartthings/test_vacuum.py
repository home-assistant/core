"""Test for the SmartThings vacuum platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command
from pysmartthings.models import HealthStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smartthings import MAIN
from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    VacuumActivity,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
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

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.VACUUM)


@pytest.mark.parametrize("device_fixture", ["da_rvc_map_01011"])
@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_START, Command.START),
        (SERVICE_PAUSE, Command.PAUSE),
        (SERVICE_RETURN_TO_BASE, Command.RETURN_TO_HOME),
    ],
)
async def test_vacuum_actions(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    command: Command,
) -> None:
    """Test vacuum actions."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        VACUUM_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "vacuum.robot_vacuum"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "01b28624-5907-c8bc-0325-8ad23f03a637",
        Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE,
        command,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["da_rvc_map_01011"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("vacuum.robot_vacuum").state == VacuumActivity.DOCKED

    await trigger_update(
        hass,
        devices,
        "01b28624-5907-c8bc-0325-8ad23f03a637",
        Capability.SAMSUNG_CE_ROBOT_CLEANER_OPERATING_STATE,
        Attribute.OPERATING_STATE,
        "error",
    )

    assert hass.states.get("vacuum.robot_vacuum").state == VacuumActivity.ERROR


@pytest.mark.parametrize("device_fixture", ["da_rvc_map_01011"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("vacuum.robot_vacuum").state == VacuumActivity.DOCKED

    await trigger_health_update(
        hass, devices, "01b28624-5907-c8bc-0325-8ad23f03a637", HealthStatus.OFFLINE
    )

    assert hass.states.get("vacuum.robot_vacuum").state == STATE_UNAVAILABLE

    await trigger_health_update(
        hass, devices, "01b28624-5907-c8bc-0325-8ad23f03a637", HealthStatus.ONLINE
    )

    assert hass.states.get("vacuum.robot_vacuum").state == VacuumActivity.DOCKED


@pytest.mark.parametrize("device_fixture", ["da_rvc_map_01011"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("vacuum.robot_vacuum").state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device_fixture", ["da_rvc_map_01011"])
async def test_fan_speed_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test fan speed state update."""
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("vacuum.robot_vacuum").attributes[ATTR_FAN_SPEED] == "maximum"
    )

    await trigger_update(
        hass,
        devices,
        "01b28624-5907-c8bc-0325-8ad23f03a637",
        Capability.ROBOT_CLEANER_TURBO_MODE,
        Attribute.ROBOT_CLEANER_TURBO_MODE,
        "extraSilence",
    )

    assert hass.states.get("vacuum.robot_vacuum").attributes[ATTR_FAN_SPEED] == "quiet"


@pytest.mark.parametrize("device_fixture", ["da_rvc_map_01011"])
async def test_vacuum_set_fan_speed(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting fan speed."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        VACUUM_DOMAIN,
        SERVICE_SET_FAN_SPEED,
        {ATTR_ENTITY_ID: "vacuum.robot_vacuum", ATTR_FAN_SPEED: "normal"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "01b28624-5907-c8bc-0325-8ad23f03a637",
        Capability.ROBOT_CLEANER_TURBO_MODE,
        Command.SET_ROBOT_CLEANER_TURBO_MODE,
        MAIN,
        "silence",
    )
