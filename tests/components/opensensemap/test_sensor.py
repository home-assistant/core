"""Tests for the openSenseMap sensor platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform, UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Restrict the integration to the sensor platform for these tests."""
    with patch("homeassistant.components.opensensemap.PLATFORMS", [Platform.SENSOR]):
        yield


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_opensensemap_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor state and registry entries via snapshot."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_missing_measurements_omit_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_opensensemap_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors are not created for measurements absent from the station."""
    mock_opensensemap_api.air_pressure = None
    mock_opensensemap_api.illuminance = None
    mock_opensensemap_api.wind_speed = None
    mock_opensensemap_api.wind_direction = None
    mock_opensensemap_api.pm1_0 = None

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    keys = {
        entry.unique_id.removeprefix(f"{mock_config_entry.unique_id}_")
        for entry in entries
    }
    assert keys == {"pm2_5", "pm10", "temperature", "humidity"}


async def test_entity_added_when_measurement_appears(
    hass: HomeAssistant,
    mock_opensensemap_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entity is added when a station starts reporting a measurement."""
    mock_opensensemap_api.illuminance = None

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.test_station_illuminance") is None

    mock_opensensemap_api.illuminance = 123.0
    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.test_station_illuminance") is not None


@pytest.mark.parametrize(
    (
        "title",
        "entity_id",
        "coordinator_attr",
        "station_unit",
        "native_unit",
        "display_unit",
        "expected_state",
    ),
    [
        pytest.param(
            "Temperature",
            "sensor.test_station_temperature",
            "temperature",
            "°F",
            UnitOfTemperature.FAHRENHEIT,
            "°C",
            (21.3 - 32) * 5 / 9,
            id="temperature_fahrenheit_to_celsius",
        ),
        pytest.param(
            "Wind Speed",
            "sensor.test_station_wind_speed",
            "wind_speed",
            "km/h",
            UnitOfSpeed.KILOMETERS_PER_HOUR,
            "km/h",
            2.5,
            id="wind_speed_kmh",
        ),
        pytest.param(
            "Air Pressure",
            "sensor.test_station_atmospheric_pressure",
            "air_pressure",
            "Pa",
            UnitOfPressure.PA,
            "hPa",
            1013.2 / 100,
            id="air_pressure_pa_to_hpa",
        ),
    ],
)
async def test_unit_detection(
    hass: HomeAssistant,
    mock_opensensemap_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    title: str,
    entity_id: str,
    coordinator_attr: str,
    station_unit: str,
    native_unit: str,
    display_unit: str,
    expected_state: float,
) -> None:
    """Test units are detected from the station and converted for the metric system."""
    # The fixture reports metric units; override one sensor's unit (the values
    # used here are the fixture's raw values) so it must be detected and
    # converted, e.g. °F -> °C, km/h stays km/h, Pa -> hPa.
    for sensor in mock_opensensemap_api.data["sensors"]:
        if sensor["title"] == title:
            sensor["unit"] = station_unit
            break

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The detector picked up the station's unit (independent of HA's conversion).
    measurement = getattr(mock_config_entry.runtime_data.data, coordinator_attr)
    assert measurement.unit == native_unit

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["unit_of_measurement"] == display_unit
    assert float(state.state) == pytest.approx(expected_state, abs=0.01)


async def test_unit_detection_ignores_value_less_sensors(
    hass: HomeAssistant,
    mock_opensensemap_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unit detection skips value-less sensors, like the library does."""
    # A value-less duplicate would shadow the real °C sensor's unit (yielding °F)
    # if detection didn't skip sensors without a measurement value.
    mock_opensensemap_api.data["sensors"].insert(
        0,
        {"title": "Temperature", "unit": "°F", "lastMeasurement": {}},
    )

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.data.temperature.unit == (
        UnitOfTemperature.CELSIUS
    )
