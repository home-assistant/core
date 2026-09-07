"""Test the Foreca sensor platform."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyforeca import ForecaError, MinutelyForecast
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.foreca.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .conftest import USAGE_TODAY

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "sensor.helsinki_air_quality_index"

# The requests-today sensor reads the current date, so without this the sensor
# tests only pass on the day the snapshot was taken.
pytestmark = pytest.mark.freeze_time(f"{USAGE_TODAY} 12:00:00", tz_offset=0)


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


async def test_air_quality_unavailable_logs_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test a lasting air quality failure is logged once, and the recovery too."""
    mock_foreca_client.air_quality_hourly.side_effect = ForecaError("no AQ here")
    await init_integration(hass, mock_config_entry)
    assert caplog.text.count("Air quality data unavailable") == 1

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert caplog.text.count("Air quality data unavailable") == 1

    mock_foreca_client.air_quality_hourly.side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert "Air quality data is available again" in caplog.text


async def test_sensors_unavailable_without_forecast_steps(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test sensors read from forecast steps go unavailable when the API returns none."""
    mock_foreca_client.forecast_hourly.return_value = []
    mock_foreca_client.forecast_daily.return_value = []
    await init_integration(hass, mock_config_entry)

    for entity_id in (
        "sensor.helsinki_precipitation_type",
        "sensor.helsinki_solar_radiation",
        "sensor.helsinki_snow_depth",
        "sensor.helsinki_sunshine_duration",
        "sensor.helsinki_forecast_confidence",
    ):
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert state.state == STATE_UNAVAILABLE, entity_id


async def test_no_station_or_nowcast_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test observation and nowcast sensors go unavailable where Foreca has no data."""
    mock_foreca_client.observation_latest.return_value = None
    mock_foreca_client.forecast_minutely.return_value = []
    await init_integration(hass, mock_config_entry)

    for entity_id in (
        "sensor.helsinki_observation_station",
        "sensor.helsinki_observed_temperature",
        "sensor.helsinki_precipitation_forecast_average",
        "sensor.helsinki_precipitation_forecast_total",
        "sensor.helsinki_precipitation_start",
    ):
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert state.state == STATE_UNAVAILABLE, entity_id

    weather = hass.states.get("weather.helsinki")
    assert weather is not None
    assert weather.state == "partlycloudy"


async def test_dry_nowcast_has_no_start_time(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test a nowcast with no rain reports zero totals and no start time."""
    mock_foreca_client.forecast_minutely.return_value = [
        MinutelyForecast(time=f"2026-09-01T17:{minute:02d}+03:00", precip_rate=0.0)
        for minute in range(10)
    ]
    await init_integration(hass, mock_config_entry)

    assert (
        hass.states.get("sensor.helsinki_precipitation_forecast_average").state == "0.0"
    )
    assert (
        hass.states.get("sensor.helsinki_precipitation_forecast_total").state == "0.0"
    )
    assert (
        hass.states.get("sensor.helsinki_precipitation_start").state
        == STATE_UNAVAILABLE
    )


async def test_usage_failure_does_not_break_the_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_foreca_client: MagicMock,
) -> None:
    """Test the weather data survives the usage endpoint failing."""
    mock_foreca_client.usage_month.side_effect = ForecaError("no usage for you")
    await init_integration(hass, mock_config_entry)

    weather = hass.states.get("weather.helsinki")
    assert weather is not None
    assert weather.state == "partlycloudy"

    state = hass.states.get("sensor.helsinki_api_requests_today")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
