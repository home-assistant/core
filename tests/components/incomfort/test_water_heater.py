"""Water heater tests for Intergas InComfort integration."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_HEATER_STATUS

from tests.common import snapshot_platform


@patch("homeassistant.components.incomfort.PLATFORMS", [Platform.WATER_HEATER])
async def test_setup_platform(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test the incomfort entities are set up correctly."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_heater_status",
    [
        MOCK_HEATER_STATUS | {"is_tapping": True},
        MOCK_HEATER_STATUS | {"is_pumping": True},
        MOCK_HEATER_STATUS | {"heater_temp": None},
        MOCK_HEATER_STATUS | {"tap_temp": None},
        MOCK_HEATER_STATUS | {"heater_temp": None, "tap_temp": None},
    ],
)
@patch("homeassistant.components.incomfort.PLATFORMS", [Platform.WATER_HEATER])
async def test_current_temperature_cases(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test incomfort entities with alternate current temperature calculation."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
