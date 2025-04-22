"""Tests for La Marzocco sensors."""

from unittest.mock import MagicMock, patch

from pylamarzocco.const import ModelName
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the La Marzocco sensors."""

    with patch("homeassistant.components.lamarzocco.PLATFORMS", [Platform.SENSOR]):
        await async_init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "device_fixture",
    [ModelName.GS3_AV, ModelName.GS3_MP, ModelName.LINEA_MINI, ModelName.LINEA_MICRA],
)
async def test_steam_ready_entity_for_all_machines(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the La Marzocco steam ready sensor for all machines."""

    serial_number = mock_lamarzocco.serial_number
    await async_init_integration(hass, mock_config_entry)

    state = hass.states.get(f"sensor.{serial_number}_steam_boiler_ready_time")

    assert state

    entry = entity_registry.async_get(state.entity_id)
    assert entry
