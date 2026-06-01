"""Tests for the openSenseMap sensor platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
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
    mock_opensensemap_api.uv = None
    mock_opensensemap_api.wind_speed = None
    mock_opensensemap_api.wind_direction = None
    mock_opensensemap_api.precipitation = None
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


async def test_temperature_fahrenheit_unit(
    hass: HomeAssistant,
    mock_opensensemap_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the native temperature unit follows the station's reported unit."""
    # Set the sensor to °F (the mock has °C) and make sure it converts to °C correctly
    for sensor in mock_opensensemap_api.data["sensors"]:
        if sensor["title"] == "Temperature":
            sensor["unit"] = "°F"
            break

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_station_temperature")
    assert state is not None
    assert state.attributes["unit_of_measurement"] == "°C"
    assert float(state.state) == pytest.approx(
        (mock_opensensemap_api.temperature - 32) * 5 / 9, abs=0.01
    )
