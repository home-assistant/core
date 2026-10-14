"""Test Home Assistant display policies over the library's typed data."""

from datetime import timedelta
from typing import Any, Literal
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from xiaomi_weather import parse_weather

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.typing import WebSocketGenerator

ENTITY_ID = "weather.beijing"


SUPPORTED_UNITS = {
    "temperature": "℃",
    "feelsLike": "℃",
    "humidity": "%",
    "pressure": "hPa",
    "visibility": "km",
    "speed": "km/h",
    "direction": "°",
}


@pytest.mark.parametrize(
    ("time", "solar_times", "expected"),
    [
        pytest.param(
            "2026-09-08T05:47:59+08:00", True, "clear-night", id="before-sunrise"
        ),
        pytest.param("2026-09-08T05:48:00+08:00", True, "sunny", id="sunrise"),
        pytest.param("2026-09-08T18:35:59+08:00", True, "sunny", id="before-sunset"),
        pytest.param("2026-09-08T18:36:00+08:00", True, "clear-night", id="sunset"),
        pytest.param(
            "2026-09-07T21:47:59+00:00", True, "clear-night", id="utc-previous-date"
        ),
        pytest.param(
            "2026-09-08T18:36:00+08:00", False, "sunny", id="missing-solar-times"
        ),
        pytest.param("2026-10-01T23:00:00+08:00", True, "sunny", id="no-matching-date"),
    ],
)
async def test_clear_condition(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    payload: dict[str, Any],
    time: str,
    solar_times: bool,
    expected: str,
) -> None:
    """Use the weather location's day boundaries, independent of the HA timezone."""
    payload["current"].update(weather="0", pubTime=time)
    payload["forecastDaily"]["sunRiseSet"]["status"] = int(not solar_times)
    client.get_weather.return_value = parse_weather(payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("units", "value"),
    [
        pytest.param(
            SUPPORTED_UNITS,
            "0",
            id="zero",
        ),
        pytest.param({}, "20", id="unsupported-units"),
        pytest.param(
            SUPPORTED_UNITS,
            "-999",
            id="missing-optional-values",
        ),
    ],
)
async def test_measurements(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    payload: dict[str, Any],
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    units: dict[str, str],
    value: str,
) -> None:
    """Preserve zero and never mislabel unsupported or missing measurements."""
    for name in ("feelsLike", "humidity", "pressure", "visibility"):
        payload["current"][name] = {
            "unit": units.get(name, "unsupported"),
            "value": value,
        }
    for name in ("speed", "direction"):
        payload["current"]["wind"][name] = {
            "unit": units.get(name, "unsupported"),
            "value": value,
        }
    payload["current"]["weather"] = "999"
    client.get_weather.return_value = parse_weather(payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({}, id="complete"),
        pytest.param({"sunRiseSet": {"value": []}}, id="missing-solar-times"),
        pytest.param({"temperature": {"value": []}}, id="missing-temperature-series"),
        pytest.param(
            {
                "precipitationProbability": {"status": 1},
                "wind": {
                    "speed": {"unit": "km/h", "value": [{"from": None, "to": None}]},
                    "direction": {"unit": "°", "value": [{"from": None, "to": None}]},
                },
            },
            id="missing-optionals",
        ),
        pytest.param({"temperature": {"unit": "F"}}, id="unsupported-temperature"),
        pytest.param(
            {"temperature": {"value": [{"from": None, "to": 0}]}}, id="night-only"
        ),
        pytest.param(
            {"temperature": {"value": [{"from": 0, "to": None}]}}, id="day-only"
        ),
        pytest.param(
            {
                "sunRiseSet": {
                    "value": [{"from": None, "to": "2026-09-08T18:36:00+08:00"}]
                }
            },
            id="sunset-only",
        ),
        pytest.param(
            {
                "sunRiseSet": {
                    "value": [{"from": "2026-09-08T05:48:00+08:00", "to": None}]
                }
            },
            id="sunrise-only",
        ),
        pytest.param(
            {"weather": {"value": [{"from": "999", "to": "999"}]}},
            id="unknown-condition",
        ),
        pytest.param(
            {"precipitationProbability": {"value": [0.5]}}, id="probability-is-percent"
        ),
        pytest.param(
            {
                "wind": {
                    "speed": {"unit": "mph", "value": [{"from": 10, "to": 20}]},
                    "direction": {"unit": "rad", "value": [{"from": 1, "to": 2}]},
                }
            },
            id="unsupported-wind",
        ),
    ],
)
@pytest.mark.parametrize("forecast_type", ["daily", "twice_daily"])
async def test_daily_projection(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    payload: dict[str, Any],
    snapshot: SnapshotAssertion,
    changes: dict[str, Any],
    forecast_type: str,
) -> None:
    """Keep each half-day independent and apply HA units and conditions."""
    daily = payload["forecastDaily"]
    for name in ("temperature", "weather", "sunRiseSet", "precipitationProbability"):
        daily[name]["value"] = daily[name]["value"][:1]
    for name in ("speed", "direction"):
        daily["wind"][name]["value"] = daily["wind"][name]["value"][:1]
    daily["weather"]["value"] = [{"from": "0", "to": "0"}]
    for key, change in changes.items():
        daily[key].update(change)
    client.get_weather.return_value = parse_weather(payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": ENTITY_ID, "type": forecast_type},
            blocking=True,
            return_response=True,
        )
        == snapshot
    )
    client.get_weather.assert_awaited_once_with("101010100", 39.9042, 116.4074)


@pytest.mark.parametrize(
    ("temperature_unit", "wind_unit", "temperatures"),
    [
        pytest.param("℃", None, [20, None, 0], id="legacy-wind"),
        pytest.param("℃", "km/h", [20, None, 0], id="explicit-wind"),
        pytest.param("℃", "mph", [20, None, 0], id="unsupported-wind"),
        pytest.param("F", None, [20, None, 0], id="unsupported-temperature"),
        pytest.param("℃", None, [], id="missing-temperature-series"),
    ],
)
async def test_hourly_projection(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    payload: dict[str, Any],
    snapshot: SnapshotAssertion,
    temperature_unit: str,
    wind_unit: str | None,
    temperatures: list[float | None],
) -> None:
    """Consume the library's time alignment without shifting temperature gaps."""
    hourly = payload["forecastHourly"]
    hourly["temperature"].update(
        unit=temperature_unit, pubTime="2026-09-08T17:00:00+08:00", value=temperatures
    )
    hourly["weather"].update(pubTime="2026-09-08T10:00:00+00:00", value=["2", "0"])
    hourly["wind"].update(
        unit=wind_unit,
        value=[
            {"datetime": "2026-09-08T11:00:00+00:00", "speed": "0", "direction": "0"},
            {"datetime": "2026-09-08T12:00:00+00:00", "speed": "2", "direction": "90"},
        ],
    )
    client.get_weather.return_value = parse_weather(payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": ENTITY_ID, "type": "hourly"},
            blocking=True,
            return_response=True,
        )
        == snapshot
    )
    client.get_weather.assert_awaited_once()


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
    client: MagicMock,
    entry: MockConfigEntry,
    forecast_type: Literal["daily", "hourly", "twice_daily"],
    payload: dict[str, Any],
    freezer: FrozenDateTimeFactory,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Subscribers receive changed forecasts, with no extra network fetch."""

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ws_client = await hass_ws_client(hass)
    await ws_client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": forecast_type,
            "entity_id": ENTITY_ID,
        }
    )
    result = await ws_client.receive_json()
    assert result["success"]
    initial = await ws_client.receive_json()
    assert initial["type"] == "event"
    payload["forecastDaily"]["temperature"]["value"][0]["from"] = "30"
    payload["forecastHourly"]["temperature"]["value"][0] = "30"
    client.get_weather.return_value = parse_weather(payload)
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    updated = await ws_client.receive_json()
    assert updated["id"] == result["id"]
    assert updated["type"] == "event"
    assert updated["event"]["forecast"][0]["temperature"] == 30
    assert client.get_weather.await_count == 2


async def test_unknown_forecast_condition(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    payload: dict[str, Any],
) -> None:
    """Unknown condition and absent low temperature remain omitted in forecasts."""
    payload["forecastDaily"]["weather"]["value"][0]["from"] = "999"
    payload["forecastDaily"]["temperature"]["value"][0]["to"] = "-999"
    client.get_weather.return_value = parse_weather(payload)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.services.async_call(
        "weather",
        "get_forecasts",
        {"entity_id": ENTITY_ID, "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert result is not None
    forecast = result[ENTITY_ID]["forecast"][0]
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
    client: MagicMock,
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
        {"entity_id": ENTITY_ID, "type": forecast_type},
        blocking=True,
        return_response=True,
    )
    assert result is not None
    forecasts = result[ENTITY_ID]["forecast"]
    assert len(forecasts) == count
    assert (
        forecasts[0].items()
        >= {"wind_speed": speed, "wind_bearing": bearing, **extra}.items()
    )
    client.get_weather.assert_awaited_once()


async def test_entities(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the weather platform state and entity registration."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param("32", "fog", id="dense-fog"),
        pytest.param("33", "snowy", id="snow"),
        pytest.param("49", "fog", id="strong-dense-fog"),
        pytest.param("54", "fog", id="moderate-haze"),
        pytest.param("55", "fog", id="heavy-haze"),
        pytest.param("56", "fog", id="severe-haze"),
        pytest.param("57", "fog", id="heavy-fog"),
        pytest.param("58", "fog", id="severe-dense-fog"),
        pytest.param("301", "rainy", id="generic-rain"),
        pytest.param("302", "snowy", id="generic-snow"),
    ],
)
@pytest.mark.parametrize("forecast_type", ["daily", "hourly", "twice_daily"])
async def test_condition_codes(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    payload: dict[str, Any],
    code: str,
    expected: str,
    forecast_type: str,
) -> None:
    """Expose weathercn conditions in observations and all forecast types."""
    payload["current"]["weather"] = code
    for period in payload["forecastDaily"]["weather"]["value"]:
        period.update({"from": code, "to": code})
    hourly = payload["forecastHourly"]["weather"]
    hourly["value"] = [code] * len(hourly["value"])
    client.get_weather.return_value = parse_weather(payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected
    result = await hass.services.async_call(
        "weather",
        "get_forecasts",
        {"entity_id": ENTITY_ID, "type": forecast_type},
        blocking=True,
        return_response=True,
    )
    assert result is not None
    assert {period["condition"] for period in result[ENTITY_ID]["forecast"]} == {
        expected
    }


@pytest.mark.parametrize(
    "publication_time",
    [
        pytest.param("2026-09-08T00:30:00+08:00", id="local-midnight"),
        pytest.param("2026-09-07T16:30:00Z", id="utc-previous-date"),
    ],
)
async def test_daily_dates_without_solar_times(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    payload: dict[str, Any],
    publication_time: str,
) -> None:
    """Keep the original daily indexes when solar data is unavailable."""
    daily = payload["forecastDaily"]
    daily["sunRiseSet"]["status"] = 1
    daily["pubTime"] = publication_time
    daily["temperature"]["value"][0] = {"from": None, "to": None}
    client.get_weather.return_value = parse_weather(payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.services.async_call(
        "weather",
        "get_forecasts",
        {"entity_id": ENTITY_ID, "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert result is not None
    forecasts = result[ENTITY_ID]["forecast"]
    assert len(forecasts) == 15
    assert forecasts[0]["datetime"] == "2026-09-07T16:00:00+00:00"
    assert forecasts[1]["datetime"] == "2026-09-08T16:00:00+00:00"
    assert forecasts[-1]["datetime"] == "2026-09-21T16:00:00+00:00"
    assert forecasts[0]["condition"] == "rainy"
    assert forecasts[1]["temperature"] == 25


async def test_daily_without_date_anchor(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    payload: dict[str, Any],
) -> None:
    """Do not invent dates when both publication and solar times are absent."""
    payload["forecastDaily"]["pubTime"] = None
    payload["forecastDaily"]["sunRiseSet"]["status"] = 1
    client.get_weather.return_value = parse_weather(payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.services.async_call(
        "weather",
        "get_forecasts",
        {"entity_id": ENTITY_ID, "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert result == {ENTITY_ID: {"forecast": []}}
