"""Test for the SmartThings cover platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability, Command, Status
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
)
from homeassistant.components.smartthings.const import MAIN
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    STATE_OPEN,
    STATE_OPENING,
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

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.COVER)


@pytest.mark.parametrize("device_fixture", ["c2c_shade"])
@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_OPEN_COVER, Command.OPEN),
        (SERVICE_CLOSE_COVER, Command.CLOSE),
    ],
)
async def test_cover_open_close(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    action: str,
    command: Command,
) -> None:
    """Test cover open and close command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        action,
        {ATTR_ENTITY_ID: "cover.curtain_1a"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "571af102-15db-4030-b76b-245a691f74a5",
        Capability.WINDOW_SHADE,
        command,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["c2c_shade"])
async def test_cover_set_position(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test cover set position command."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.curtain_1a", ATTR_POSITION: 25},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "571af102-15db-4030-b76b-245a691f74a5",
        Capability.SWITCH_LEVEL,
        Command.SET_LEVEL,
        MAIN,
        argument=25,
    )


@pytest.mark.parametrize("device_fixture", ["c2c_shade"])
async def test_cover_battery(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test battery extra state attribute."""
    devices.get_device_status.return_value[MAIN][Capability.BATTERY] = {
        Attribute.BATTERY: Status(50)
    }
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.curtain_1a")
    assert state
    assert state.attributes[ATTR_BATTERY_LEVEL] == 50


@pytest.mark.parametrize("device_fixture", ["c2c_shade"])
async def test_cover_battery_updating(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test battery extra state attribute."""
    devices.get_device_status.return_value[MAIN][Capability.BATTERY] = {
        Attribute.BATTERY: Status(50)
    }
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("cover.curtain_1a")
    assert state
    assert state.attributes[ATTR_BATTERY_LEVEL] == 50

    await trigger_update(
        hass,
        devices,
        "571af102-15db-4030-b76b-245a691f74a5",
        Capability.BATTERY,
        Attribute.BATTERY,
        49,
    )

    state = hass.states.get("cover.curtain_1a")
    assert state
    assert state.attributes[ATTR_BATTERY_LEVEL] == 49


@pytest.mark.parametrize("device_fixture", ["c2c_shade"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("cover.curtain_1a").state == STATE_OPEN

    await trigger_update(
        hass,
        devices,
        "571af102-15db-4030-b76b-245a691f74a5",
        Capability.WINDOW_SHADE,
        Attribute.WINDOW_SHADE,
        "opening",
    )

    assert hass.states.get("cover.curtain_1a").state == STATE_OPENING


@pytest.mark.parametrize("device_fixture", ["c2c_shade"])
async def test_position_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test position update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("cover.curtain_1a").attributes[ATTR_CURRENT_POSITION] == 100

    await trigger_update(
        hass,
        devices,
        "571af102-15db-4030-b76b-245a691f74a5",
        Capability.SWITCH_LEVEL,
        Attribute.LEVEL,
        50,
    )

    assert hass.states.get("cover.curtain_1a").attributes[ATTR_CURRENT_POSITION] == 50
