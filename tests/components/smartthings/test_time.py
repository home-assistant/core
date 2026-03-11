"""Test for the SmartThings time platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smartthings import MAIN
from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TIME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_smartthings_entities, trigger_update

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

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.TIME)


@pytest.mark.parametrize("device_fixture", ["da_rvc_map_01011"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("time.robot_vacuum_do_not_disturb_end_time").state == "06:00:00"
    )

    await trigger_update(
        hass,
        devices,
        "01b28624-5907-c8bc-0325-8ad23f03a637",
        Capability.CUSTOM_DO_NOT_DISTURB_MODE,
        Attribute.END_TIME,
        "0800",
    )

    assert (
        hass.states.get("time.robot_vacuum_do_not_disturb_end_time").state == "08:00:00"
    )


@pytest.mark.parametrize("device_fixture", ["da_rvc_map_01011"])
async def test_set_value(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting a value."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "time.robot_vacuum_do_not_disturb_end_time",
            ATTR_TIME: "09:00:00",
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "01b28624-5907-c8bc-0325-8ad23f03a637",
        Capability.CUSTOM_DO_NOT_DISTURB_MODE,
        Command.SET_DO_NOT_DISTURB_MODE,
        MAIN,
        argument={
            "mode": "on",
            "startTime": "2200",
            "endTime": "0900",
        },
    )


@pytest.mark.parametrize("device_fixture", ["da_rvc_map_01011"])
async def test_dnd_mode_updates(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting a value."""
    await setup_integration(hass, mock_config_entry)

    await trigger_update(
        hass,
        devices,
        "01b28624-5907-c8bc-0325-8ad23f03a637",
        Capability.CUSTOM_DO_NOT_DISTURB_MODE,
        Attribute.DO_NOT_DISTURB,
        "off",
    )

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "time.robot_vacuum_do_not_disturb_end_time",
            ATTR_TIME: "09:00:00",
        },
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "01b28624-5907-c8bc-0325-8ad23f03a637",
        Capability.CUSTOM_DO_NOT_DISTURB_MODE,
        Command.SET_DO_NOT_DISTURB_MODE,
        MAIN,
        argument={
            "mode": "off",
            "startTime": "2200",
            "endTime": "0900",
        },
    )
