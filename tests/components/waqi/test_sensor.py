"""Test the World Air Quality Index (WAQI) sensor."""

from unittest.mock import AsyncMock

from aiowaqi import WAQIAirQuality
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.waqi.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_load_json_object_fixture, snapshot_platform


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


async def test_dominant_pollutant_unavailable_when_missing_measurement(
    hass: HomeAssistant,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test dominant pollutant is unknown when that pollutant has no measurement."""
    payload = await async_load_json_object_fixture(hass, "air_quality_sensor.json", DOMAIN)
    payload["dominentpol"] = "pm25"
    payload["iaqi"].pop("pm25")
    mock_waqi.return_value.get_by_station_number.return_value = WAQIAirQuality.from_dict(
        payload
    )

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.de_jongweg_utrecht_dominant_pollutant")
    assert state is not None
    assert state.state == "unknown"
