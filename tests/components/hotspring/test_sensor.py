"""Tests for the Hot Spring sensor platform."""

import math

from hotspring import Spa, TemperatureUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
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
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor platform state."""
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


def _enable_freshwater_iq(device_fixture: Spa) -> None:
    """Configure the spa fixture with installed FreshWater IQ sensors."""
    device_fixture.freshwater_iq.installed = True
    device_fixture.freshwater_iq.ph = 7.7
    device_fixture.freshwater_iq.chlorine = 23.1
    device_fixture.freshwater_iq.orp = 793
    device_fixture.freshwater_iq.sensor_life_percentage = 79.06


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hotspring")
async def test_freshwater_iq_sensors_installed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the FreshWater IQ sensors when the IQ system is installed."""
    _enable_freshwater_iq(device_fixture)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_hotspring")
async def test_freshwater_iq_sensors_absent_without_iq(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that no FreshWater IQ sensors are created when IQ is not installed."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    for entity_id in ENTITY_IDS:
        assert hass.states.get(entity_id) is None


@pytest.mark.parametrize(
    ("attribute", "value", "expected_state"),
    [
        pytest.param("ph", 0.0, "0.0", id="valid_zero_ph"),
        pytest.param("chlorine", 0.0, "0.0", id="valid_zero_chlorine"),
        pytest.param("sensor_life_percentage", 0.0, "0.0", id="valid_zero_sensor_life"),
        pytest.param("ph", None, STATE_UNKNOWN, id="unknown_ph"),
        pytest.param("chlorine", None, STATE_UNKNOWN, id="unknown_chlorine"),
        pytest.param("orp", None, STATE_UNKNOWN, id="unknown_orp"),
        pytest.param(
            "sensor_life_percentage", None, STATE_UNKNOWN, id="unknown_sensor_life"
        ),
        pytest.param("ph", math.inf, STATE_UNKNOWN, id="nonfinite_ph"),
        pytest.param("chlorine", math.inf, STATE_UNKNOWN, id="nonfinite_chlorine"),
        pytest.param(
            "sensor_life_percentage",
            math.inf,
            STATE_UNKNOWN,
            id="nonfinite_sensor_life",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hotspring")
async def test_freshwater_iq_reading_validity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_fixture: Spa,
    attribute: str,
    value: float | None,
    expected_state: str,
) -> None:
    """Test library readings are exposed and missing measurements are unknown."""
    _enable_freshwater_iq(device_fixture)
    setattr(device_fixture.freshwater_iq, attribute, value)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    entity_ids = {
        "ph": "sensor.connectedspa_ddeeff_ph",
        "chlorine": "sensor.connectedspa_ddeeff_chlorine",
        "orp": "sensor.connectedspa_ddeeff_oxidation_reduction_potential",
        "sensor_life_percentage": "sensor.connectedspa_ddeeff_sensor_life",
    }
    assert hass.states.get(entity_ids[attribute]).state == expected_state
