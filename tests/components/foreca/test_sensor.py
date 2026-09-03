"""Test the Foreca sensor platform."""

from unittest.mock import MagicMock, patch

from pyforeca import ForecaError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "sensor.helsinki_air_quality_index"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_foreca_client")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the states of the air quality sensors."""
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_foreca_client")
@pytest.mark.parametrize(
    "key",
    ["aqi_co", "aqi_no2", "aqi_o3", "aqi_so2", "aqi_pm10", "aqi_pm2p5"],
)
async def test_pollutant_sensors_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    key: str,
) -> None:
    """Test the per-pollutant sub-index sensors are disabled by default."""
    with patch("homeassistant.components.foreca.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mock_config_entry)

    entry = entity_registry.async_get_entity_id(
        Platform.SENSOR, "foreca", f"{mock_config_entry.entry_id}-{key}"
    )
    assert entry is not None
    assert entity_registry.async_get(entry).disabled_by is (
        er.RegistryEntryDisabler.INTEGRATION
    )


async def test_air_quality_failure_keeps_weather(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test air quality sensors go unavailable without affecting the weather entity."""
    mock_foreca_client.air_quality_hourly.side_effect = ForecaError("no AQ here")
    mock_foreca_client.air_quality_daily.side_effect = ForecaError("no AQ here")
    await init_integration(hass, mock_config_entry)

    weather = hass.states.get("weather.helsinki")
    assert weather is not None
    assert weather.state == "partlycloudy"

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
