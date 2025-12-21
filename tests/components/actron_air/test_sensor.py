"""Tests for the Actron Air sensor platform."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entities(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor entities."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "expected_value"),
    [
        ("sensor.test_system_compressor_chasing_temperature", "24.0"),
        ("sensor.test_system_compressor_live_temperature", "23.5"),
        ("sensor.test_system_compressor_speed", "1500"),
        ("sensor.test_system_compressor_power", "2500"),
        ("sensor.test_system_outdoor_temperature", "28.5"),
        ("sensor.zone_controller_3_battery", "85"),
        ("sensor.zone_controller_3_humidity", "45"),
        ("sensor.zone_controller_3_temperature", "22.5"),
    ],
)
async def test_sensor_values(
    hass: HomeAssistant,
    mock_actron_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    expected_value: str,
) -> None:
    """Test sensor values."""
    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_value
