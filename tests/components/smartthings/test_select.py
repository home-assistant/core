"""Test for the SmartThings select platform."""

from unittest.mock import AsyncMock

from pysmartthings import Capability, Command
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.smartthings import MAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration, snapshot_smartthings_entities

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

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.SELECT)


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_select_option(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test select option."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.washer_rinse_cycles", ATTR_OPTION: "3"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "f984b91d-f250-9d42-3436-33f09a422a47",
        Capability.CUSTOM_WASHER_RINSE_CYCLES,
        Command.SET_WASHER_RINSE_CYCLES,
        MAIN,
        argument="3",
    )
