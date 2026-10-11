"""Integration lifecycle, weather service and recovery tests."""

from dataclasses import replace
from datetime import timedelta
from typing import Any, Literal
from unittest.mock import AsyncMock, Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from xiaomi_weather import XiaomiWeatherError, parse_weather

from homeassistant.components.weather import DATA_COMPONENT, WeatherEntityStateAttribute
from homeassistant.components.xiaomi_weather.weather import XiaomiWeather
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_forecast_unload(
    hass: HomeAssistant,
    client: AsyncMock,
    entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup forecast unload."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get("weather.beijing")
    assert state is not None
    assert state.state == "partlycloudy"
    assert state.attributes["temperature"] == 20
    assert state.attributes["humidity"] == 71
    client.assert_awaited_once()
    entities = entity_registry.entities
    assert (
        len([e for e in entities.values() if e.config_entry_id == entry.entry_id]) == 1
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("failure", "unit"),
    [
        pytest.param(XiaomiWeatherError, "℃", id="request-error"),
        pytest.param(None, "F", id="unsupported-temperature"),
    ],
)
async def test_setup_retry(
    hass: HomeAssistant,
    client: AsyncMock,
    entry: MockConfigEntry,
    failure: type[XiaomiWeatherError] | None,
    unit: str,
) -> None:
    """Retry setup when required current weather is unusable."""
    client.side_effect = failure
    data = client.return_value
    client.return_value = replace(
        data,
        current=replace(
            data.current, temperature=replace(data.current.temperature, unit=unit)
        ),
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("failure", "unit"),
    [
        pytest.param(XiaomiWeatherError, "℃", id="request-error"),
        pytest.param(None, "F", id="unsupported-temperature"),
    ],
)
@pytest.mark.usefixtures("entity_registry")
async def test_update_and_recovery(
    hass: HomeAssistant,
    client: AsyncMock,
    entry: MockConfigEntry,
    failure: type[XiaomiWeatherError] | None,
    unit: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update and recovery."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    client.side_effect = failure
    data = client.return_value
    client.return_value = replace(
        data,
        current=replace(
            data.current, temperature=replace(data.current.temperature, unit=unit)
        ),
    )
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get("weather.beijing")
    assert state is not None and state.state == "unavailable"
    client.side_effect = None
    client.return_value = replace(
        client.return_value,
        current=replace(
            client.return_value.current,
            temperature=replace(
                client.return_value.current.temperature, value=22, unit="℃"
            ),
        ),
    )
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get("weather.beijing")
    assert state is not None and state.attributes["temperature"] == 22


async def test_poll_and_unload(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry
) -> None:
    """One scheduled request serves all entities; unloading cancels the next one."""

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    client.assert_awaited_once()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=16))
    await hass.async_block_till_done()
    assert client.await_count == 2
    assert await hass.config_entries.async_unload(entry.entry_id)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=32))
    await hass.async_block_till_done()
    assert client.await_count == 2


@pytest.mark.parametrize(
    "forecast_type",
    [
        pytest.param("daily", id="daily"),
        pytest.param("hourly", id="hourly"),
        pytest.param("twice_daily", id="twice-daily"),
    ],
)
async def test_forecast_subscription(
    hass: HomeAssistant,
    client: AsyncMock,
    entry: MockConfigEntry,
    forecast_type: Literal["daily", "hourly", "twice_daily"],
    payload: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Subscribers receive changed forecasts, with no extra network fetch."""

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity = hass.data[DATA_COMPONENT].get_entity("weather.beijing")
    assert isinstance(entity, XiaomiWeather)
    listener = Mock()
    unsubscribe = entity.async_subscribe_forecast(forecast_type, listener)
    payload["forecastDaily"]["temperature"]["value"][0]["from"] = "30"
    payload["forecastHourly"]["temperature"]["value"][0] = "30"
    client.return_value = parse_weather(payload)
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    listener.assert_called_once()
    assert listener.call_args.args[0][0]["temperature"] == 30
    assert client.await_count == 2
    unsubscribe()


async def test_independent_locations(
    hass: HomeAssistant, client: AsyncMock, entry: MockConfigEntry
) -> None:
    """Unloading one location leaves the other location operational."""
    other = MockConfigEntry(
        domain="xiaomi_weather",
        title="Shanghai",
        unique_id="101020100",
        data={
            "name": "Shanghai",
            "city_id": "101020100",
            "latitude": 31.2,
            "longitude": 121.5,
        },
    )
    for config_entry in (entry, other):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert client.await_count == 2
    assert await hass.config_entries.async_unload(entry.entry_id)
    state = hass.states.get("weather.shanghai")
    assert state is not None and state.state == "partlycloudy"


async def test_unknown_forecast_condition(
    hass: HomeAssistant,
    client: AsyncMock,
    entry: MockConfigEntry,
    payload: dict[str, Any],
) -> None:
    """Unknown condition and absent low temperature remain omitted in forecasts."""
    payload["forecastDaily"]["weather"]["value"][0]["from"] = "999"
    payload["forecastDaily"]["temperature"]["value"][0]["to"] = "-999"
    client.return_value = parse_weather(payload)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.services.async_call(
        "weather",
        "get_forecasts",
        {"entity_id": "weather.beijing", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert result is not None
    forecast = result["weather.beijing"]["forecast"][0]
    assert "condition" not in forecast
    assert "templow" not in forecast


@pytest.mark.parametrize(
    ("forecast_type", "count", "speed", "bearing", "extra"),
    [
        pytest.param("daily", 15, 6, 27, {"precipitation_probability": 0}, id="daily"),
        pytest.param("hourly", 23, 4.6, 37.05, {}, id="hourly"),
        pytest.param("twice_daily", 30, 6, 27, {"is_daytime": True}, id="twice-daily"),
    ],
)
async def test_forecast(
    hass: HomeAssistant,
    client: AsyncMock,
    entry: MockConfigEntry,
    forecast_type: str,
    count: int,
    speed: float,
    bearing: float,
    extra: dict[str, bool | int],
) -> None:
    """Expose cached forecasts through the standard weather action."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.services.async_call(
        "weather",
        "get_forecasts",
        {"entity_id": "weather.beijing", "type": forecast_type},
        blocking=True,
        return_response=True,
    )
    assert result is not None
    forecasts = result["weather.beijing"]["forecast"]
    assert len(forecasts) == count
    assert (
        forecasts[0].items()
        >= {"wind_speed": speed, "wind_bearing": bearing, **extra}.items()
    )
    client.assert_awaited_once()


async def test_standard_weather_state_and_units(
    hass: HomeAssistant,
    client: AsyncMock,
    entry: MockConfigEntry,
    payload: dict[str, Any],
    entity_registry: er.EntityRegistry,
) -> None:
    """Rich source data stays separate; HA converts native weather measurements."""
    current = payload["current"]
    current["temperature"]["value"] = "20"
    current["feelsLike"]["value"] = "10"
    current["visibility"]["value"] = "16.09344"
    current["wind"]["speed"]["value"] = "16.09344"
    current["pressure"]["value"] = "1015.9166"
    payload["alerts"] = [{"title": "模拟预警"}]
    client.return_value = parse_weather(payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("weather.beijing")
    assert state is not None
    allowed = set(WeatherEntityStateAttribute) | {
        "attribution",
        "friendly_name",
        "supported_features",
    }
    assert state.attributes.keys() <= allowed
    assert state.attributes["temperature"] == 20
    assert state.attributes["apparent_temperature"] == 10
    assert state.attributes["temperature_unit"] == "°C"
    assert not {"ozone", "cloud_coverage", "dew_point", "wind_gust_speed"} & (
        state.attributes.keys()
    )

    entity_registry.async_update_entity_options(
        "weather.beijing",
        "weather",
        {
            "temperature_unit": "°F",
            "pressure_unit": "inHg",
            "wind_speed_unit": "mph",
            "visibility_unit": "mi",
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("weather.beijing")
    assert state is not None
    assert state.attributes.keys() <= allowed
    for key, expected in {
        "temperature": 68,
        "apparent_temperature": 50,
        "pressure": 30,
        "wind_speed": 10,
        "visibility": 10,
    }.items():
        assert state.attributes[key] == pytest.approx(expected)
    assert state.attributes["temperature_unit"] == "°F"
    client.assert_awaited_once()
