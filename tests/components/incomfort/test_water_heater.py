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
    ("mock_heater_status", "current_temperature"),
    [
        (MOCK_HEATER_STATUS, 35.3),
        (MOCK_HEATER_STATUS | {"is_tapping": True}, 30.2),
        (MOCK_HEATER_STATUS | {"is_pumping": True}, 35.3),
        (MOCK_HEATER_STATUS | {"heater_temp": None}, 30.2),
        (MOCK_HEATER_STATUS | {"tap_temp": None}, 35.3),
        (MOCK_HEATER_STATUS | {"heater_temp": None, "tap_temp": None}, None),
    ],
    ids=[
        "both_temps_available_choose_highest",
        "is_tapping_choose_tapping_temp",
        "is_pumping_choose_heater_temp",
        "heater_temp_not_available_choose_tapping_temp",
        "tapping_temp_not_available_choose_heater_temp",
        "tapping_and_heater_temp_not_available_unknown",
    ],
)
@patch("homeassistant.components.incomfort.PLATFORMS", [Platform.WATER_HEATER])
async def test_current_temperature_cases(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: ConfigEntry,
    current_temperature: float | None,
) -> None:
    """Test incomfort entities with alternate current temperature calculation.

    The boilers current temperature is calculated from the testdata:
    heater_temp: 35.34
    tap_temp: 30.21

    It is based on the operating mode as the boiler can heat tap water or
    the house.
    """
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert (state := hass.states.get("water_heater.boiler")) is not None
    assert state.attributes.get("current_temperature") == current_temperature
