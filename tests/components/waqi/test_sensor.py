"""Test the World Air Quality Index (WAQI) sensor."""

from unittest.mock import AsyncMock

from aiowaqi import WAQIAirQuality
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.waqi.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    snapshot_platform,
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the World Air Quality Index (WAQI) sensor."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_unavailable_when_aqi_missing(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors report unavailable when AQI data is missing."""
    problematic = WAQIAirQuality.from_dict(
        await async_load_json_object_fixture(
            hass, "air_quality_sensor_aqi_unavailable.json", DOMAIN
        )
    )
    mock_waqi.get_by_station_number.return_value = problematic

    await setup_integration(hass, mock_config_entry)

    aqi_state = hass.states.get("sensor.de_jongweg_utrecht_air_quality_index")
    assert aqi_state is not None
    assert aqi_state.state == STATE_UNAVAILABLE

    dominant_state = hass.states.get("sensor.de_jongweg_utrecht_dominant_pollutant")
    assert dominant_state is not None
    assert dominant_state.state == STATE_UNAVAILABLE
