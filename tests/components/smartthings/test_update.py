"""Test for the SmartThings update platform."""

from unittest.mock import AsyncMock

from pysmartthings.models import Capability, Command
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
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

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.UPDATE)


@pytest.mark.parametrize("fixture", ["contact_sensor"])
async def test_installing_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test installing an update."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.front_door_open_closed_sensor"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "2d9a892b-1c93-45a5-84cb-0e81889498c6",
        Capability.FIRMWARE_UPDATE,
        Command.UPDATE_FIRMWARE,
    )
