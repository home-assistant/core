"""Test for the SmartThings switch platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.smartthings.const import MAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
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

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.SWITCH)


@pytest.mark.parametrize("device_fixture", ["c2c_arlo_pro_3_switch"])
@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_TURN_ON, Command.ON),
        (SERVICE_TURN_OFF, Command.OFF),
    ],
)
async def test_switch_turn_on_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    command: Command,
) -> None:
    """Test switch turn on and off command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "switch.2nd_floor_hallway"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "10e06a70-ee7d-4832-85e9-a0a06a7a05bd", Capability.SWITCH, command, MAIN
    )


@pytest.mark.parametrize("device_fixture", ["c2c_arlo_pro_3_switch"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("switch.2nd_floor_hallway").state == STATE_ON

    await trigger_update(
        hass,
        devices,
        "10e06a70-ee7d-4832-85e9-a0a06a7a05bd",
        Capability.SWITCH,
        Attribute.SWITCH,
        "off",
    )

    assert hass.states.get("switch.2nd_floor_hallway").state == STATE_OFF
