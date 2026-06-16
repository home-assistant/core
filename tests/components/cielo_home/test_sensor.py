"""Tests for the Cielo Home sensor platform."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.usefixtures("mock_cielo_device_api")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_cielo_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all sensor entities."""
    with patch("homeassistant.components.cielo_home.PLATFORMS", [Platform.SENSOR]):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("temperature_unit", "hass_units", "expected_unit"),
    [
        pytest.param(
            "°F",
            US_CUSTOMARY_SYSTEM,
            UnitOfTemperature.FAHRENHEIT,
            id="fahrenheit",
        ),
        pytest.param(
            "unknown",
            None,
            UnitOfTemperature.CELSIUS,
            id="unknown_unit",
        ),
        pytest.param(
            None,
            None,
            UnitOfTemperature.CELSIUS,
            id="none_unit",
        ),
    ],
)
async def test_temperature_sensor_unit(
    hass: HomeAssistant,
    mock_cielo_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_cielo_device_api: MagicMock,
    temperature_unit: str | None,
    hass_units: object | None,
    expected_unit: str,
) -> None:
    """Test temperature sensor reports the correct unit."""
    mock_cielo_device_api.temperature_unit.return_value = temperature_unit
    if hass_units is not None:
        hass.config.units = hass_units

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room_living_room_temperature")
    assert state is not None
    assert state.attributes.get("unit_of_measurement") == expected_unit
