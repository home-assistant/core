"""Tests for the Hot Spring sensor platform."""

from hotspring import Spa, TemperatureUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

ENTITY_IDS = (
    "sensor.connectedspa_ddeeff_ph",
    "sensor.connectedspa_ddeeff_chlorine",
    "sensor.connectedspa_ddeeff_oxidation_reduction_potential",
    "sensor.connectedspa_ddeeff_sensor_life",
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hotspring")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor platform state."""
    device_fixture.freshwater_iq.installed = True
    device_fixture.freshwater_iq.ph = 7.7
    device_fixture.freshwater_iq.chlorine = 23.1
    device_fixture.freshwater_iq.orp = 793
    device_fixture.freshwater_iq.sensor_life_percentage = 79.06
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hotspring")
async def test_temperature_sensor_celsius(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the temperature sensor when the spa is configured in Celsius."""
    device_fixture.heater.temperature_unit = TemperatureUnit.CELSIUS
    device_fixture.heater.current_temperature = 38.5
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    assert hass.states.get("sensor.connectedspa_ddeeff_current_temperature") == snapshot


@pytest.mark.usefixtures("mock_hotspring")
async def test_freshwater_iq_sensors_absent_without_iq(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that no FreshWater IQ sensors are created when IQ is not installed."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    for entity_id in ENTITY_IDS:
        assert hass.states.get(entity_id) is None
