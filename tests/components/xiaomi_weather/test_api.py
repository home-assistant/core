"""Client transport and parsing contract tests."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

from aiohttp import ClientConnectionError, ClientSession
import pytest

from homeassistant.components.xiaomi_weather.api import (
    URL,
    XiaomiWeatherClient,
    XiaomiWeatherError,
    number,
    parse_weather,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from tests.test_util.aiohttp import AiohttpClientMocker


def test_live_fixture(payload: dict[str, Any]) -> None:
    """Check actual units, array alignment and timezone conversion."""
    data = parse_weather(payload)
    assert data.temperature == 20
    assert data.humidity == 71
    assert data.pressure == 1014
    assert data.wind_speed == 6
    assert len(data.daily) == 15
    assert len(data.hourly) == 23
    assert data.daily[0].temperature == 21
    assert data.daily[0].low == 16
    assert data.daily[0].time == datetime(2026, 9, 7, 16, tzinfo=UTC)
    assert data.hourly[0].time == datetime(2026, 9, 8, 5, tzinfo=UTC)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "NaN",
        "inf",
        "-inf",
        -999,
        True,
        {},
        "bad",
        pytest.param(10**400, id="positive-overflow"),
        pytest.param(-(10**400), id="negative-overflow"),
    ],
)
def test_invalid_numbers(value: object) -> None:
    """Test invalid numbers."""
    assert number(value) is None


@pytest.mark.parametrize("value", [0, "0", 0.0])
def test_zero(value: object) -> None:
    """Test zero."""
    assert number(value) == 0


@pytest.mark.parametrize("bad", [None, {}, [], {"current": {}}, {"current": None}])
def test_invalid_payload(bad: object) -> None:
    """Test invalid payload."""
    with pytest.raises(XiaomiWeatherError):
        parse_weather(bad)


def test_optional_data(payload: dict[str, Any]) -> None:
    """Test optional data."""
    data = parse_weather({"current": payload["current"]})
    assert data.daily == ()
    assert data.hourly == ()


@pytest.mark.parametrize(
    ("key", "attribute"),
    [
        pytest.param("humidity", "humidity", id="humidity"),
        pytest.param("pressure", "pressure", id="pressure"),
        pytest.param("feelsLike", "apparent_temperature", id="feels-like"),
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="null"),
        pytest.param([], id="list"),
        pytest.param("invalid", id="string"),
    ],
)
def test_malformed_optional_measurement(
    payload: dict[str, Any], key: str, attribute: str, value: object
) -> None:
    """A malformed optional measurement must not discard valid weather data."""
    expected = replace(parse_weather(payload), **{attribute: None})
    payload["current"][key] = value
    assert parse_weather(payload) == expected


def test_unknown_condition(payload: dict[str, Any]) -> None:
    """Test unknown condition."""
    payload["current"]["weather"] = "9999"
    assert parse_weather(payload).condition is None


@pytest.mark.parametrize(
    ("time", "expected"),
    [
        ("2026-09-08T05:47:00+08:00", "clear-night"),
        ("2026-09-08T05:48:00+08:00", "sunny"),
        ("2026-09-08T18:36:00+08:00", "clear-night"),
    ],
)
def test_day_night(payload: dict[str, Any], time: str, expected: str) -> None:
    """Test day night."""
    payload["current"].update(weather="0", pubTime=time)
    assert parse_weather(payload).condition == expected


def test_array_gaps(payload: dict[str, Any]) -> None:
    """Test array gaps."""
    payload["forecastDaily"]["temperature"]["value"][0]["from"] = ""
    payload["forecastDaily"]["weather"]["value"] = []
    payload["forecastHourly"]["temperature"]["value"][0] = None
    payload["forecastHourly"]["weather"]["value"] = []
    data = parse_weather(payload)
    assert len(data.daily) == 14
    assert data.daily[0].condition is None
    assert len(data.hourly) == 22
    assert data.hourly[0].time.hour == 6


@pytest.mark.parametrize(
    ("section", "empty_forecasts"),
    [
        pytest.param("forecastDaily", ("daily", "twice_daily"), id="daily"),
        pytest.param("forecastHourly", ("hourly",), id="hourly"),
    ],
)
@pytest.mark.parametrize(
    "unit_fields",
    [
        pytest.param({}, id="missing"),
        pytest.param({"unit": None}, id="null"),
        pytest.param({"unit": "F"}, id="unsupported"),
    ],
)
def test_invalid_forecast_temperature_unit(
    payload: dict[str, Any],
    section: str,
    empty_forecasts: tuple[str, ...],
    unit_fields: dict[str, str | None],
) -> None:
    """Omit only forecasts with unverified units and retain other weather data."""
    expected = replace(parse_weather(payload), **dict.fromkeys(empty_forecasts, ()))
    temperatures = payload[section]["temperature"]
    del temperatures["unit"]
    temperatures.update(unit_fields)
    assert parse_weather(payload) == expected


@pytest.mark.parametrize(
    "unit_fields",
    [
        pytest.param({}, id="missing"),
        pytest.param({"unit": None}, id="null"),
        pytest.param({"unit": "F"}, id="unsupported"),
    ],
)
def test_invalid_current_temperature_unit(
    payload: dict[str, Any], unit_fields: dict[str, str | None]
) -> None:
    """Current temperature still requires a verified Celsius unit."""
    temperature = payload["current"]["temperature"]
    del temperature["unit"]
    temperature.update(unit_fields)
    with pytest.raises(XiaomiWeatherError, match="Missing current temperature"):
        parse_weather(payload)


def test_naive_timestamp(payload: dict[str, Any]) -> None:
    """Test naive timestamp."""
    payload["current"]["pubTime"] = "2026-09-08T12:00:00"
    with pytest.raises(XiaomiWeatherError):
        parse_weather(payload)


def test_provider_status(payload: dict[str, Any]) -> None:
    """Test provider status."""
    for section in ("forecastDaily", "forecastHourly"):
        payload[section]["status"] = 1
    data = parse_weather(payload)
    assert not data.daily and not data.hourly


async def test_http_success(
    hass: HomeAssistant, payload: dict[str, Any], aioclient_mock: AiohttpClientMocker
) -> None:
    """Request the configured weather location through the injected session."""
    aioclient_mock.get(URL, json=payload)
    session = async_get_clientsession(hass)
    result = await XiaomiWeatherClient(
        session, "101010100", 39.9, 116.4
    ).async_get_weather()
    assert result.temperature == 20
    assert aioclient_mock.call_count == 1
    query = aioclient_mock.mock_calls[0][1].query
    assert dict(query) == {
        "locationKey": "weathercn:101010100",
        "latitude": "39.9",
        "longitude": "116.4",
        "days": "15",
        "appKey": "weather20151024",
        "sign": "zUFJoAR2ZVrDy1vF3D07",
        "isGlobal": "false",
        "locale": "zh_cn",
    }


@pytest.mark.parametrize(
    ("status", "body"),
    [
        pytest.param(429, "limited", id="rate-limit"),
        pytest.param(500, "error", id="server-error"),
        pytest.param(200, "not-json", id="invalid-json"),
    ],
)
async def test_http_failure(
    hass: HomeAssistant, status: int, body: str, aioclient_mock: AiohttpClientMocker
) -> None:
    """Normalize HTTP failures and malformed JSON without retrying."""
    aioclient_mock.get(URL, status=status, text=body)
    session = async_get_clientsession(hass)
    with pytest.raises(XiaomiWeatherError):
        await XiaomiWeatherClient(session, "101010100", 39.9, 116.4).async_get_weather()
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize("failure", [TimeoutError(), ClientConnectionError()])
async def test_transport_failure(failure: Exception) -> None:
    """Test transport failure."""
    session = MagicMock(spec=ClientSession)
    session.get.side_effect = failure
    with pytest.raises(XiaomiWeatherError):
        await XiaomiWeatherClient(session, "101010100", 39.9, 116.4).async_get_weather()


@pytest.mark.parametrize(
    ("section", "key", "forecast"),
    [
        pytest.param("forecastDaily", "temperature", "daily", id="daily-temperature"),
        pytest.param("forecastDaily", "sunRiseSet", "daily", id="daily-sun-times"),
        pytest.param(
            "forecastHourly", "temperature", "hourly", id="hourly-temperature"
        ),
    ],
)
def test_failed_subseries(
    payload: dict[str, Any], section: str, key: str, forecast: str
) -> None:
    """Omit periods without valid temperatures or required dates."""
    payload[section][key]["status"] = 1
    assert getattr(parse_weather(payload), forecast) == ()


@pytest.mark.parametrize(
    ("section", "forecast"),
    [
        pytest.param("forecastDaily", "daily", id="daily"),
        pytest.param("forecastHourly", "hourly", id="hourly"),
    ],
)
def test_failed_conditions(
    payload: dict[str, Any], section: str, forecast: str
) -> None:
    """Keep forecast temperatures when only the condition series fails."""
    payload[section]["weather"]["status"] = 1
    assert all(
        item.condition is None for item in getattr(parse_weather(payload), forecast)
    )


@pytest.mark.parametrize(
    "condition_entry",
    [
        pytest.param(None, id="null"),
        pytest.param({}, id="missing-condition"),
        pytest.param("invalid", id="invalid-type"),
        pytest.param({"status": 1, "from": "0", "to": "0"}, id="failed-entry"),
    ],
)
def test_malformed_daily_condition(
    payload: dict[str, Any], condition_entry: object
) -> None:
    """Keep valid weather and forecast periods when a condition is malformed."""
    expected = parse_weather(payload)
    payload["forecastDaily"]["weather"]["value"][0] = condition_entry

    data = parse_weather(payload)

    assert data.temperature == expected.temperature
    assert len(data.daily) == len(expected.daily)
    assert data.daily[0].temperature == expected.daily[0].temperature
    assert data.daily[0].low == expected.daily[0].low
    assert data.daily[0].condition is None
    assert data.daily[1:] == expected.daily[1:]
    assert len(data.twice_daily) == len(expected.twice_daily)
    assert data.twice_daily[0].condition is None
    assert data.twice_daily[1].condition is None
    assert data.hourly == expected.hourly


def test_misaligned_hourly_weather(payload: dict[str, Any]) -> None:
    """Test misaligned hourly weather."""
    payload["forecastHourly"]["weather"]["pubTime"] = "2026-09-08T14:00:00+08:00"
    assert all(item.condition is None for item in parse_weather(payload).hourly)


@pytest.mark.parametrize(
    ("item", "daily_count", "periods"),
    [
        pytest.param({"from": "21"}, 15, [True], id="missing-low"),
        pytest.param({"to": "16"}, 14, [False], id="missing-high"),
        pytest.param(None, 14, [], id="null"),
        pytest.param({}, 14, [], id="empty"),
        pytest.param("bad", 14, [], id="invalid-type"),
    ],
)
def test_incomplete_daily_temperature(
    payload: dict[str, Any], item: object, daily_count: int, periods: list[bool]
) -> None:
    """Discard only forecast periods without a usable temperature."""
    expected = parse_weather(payload)
    payload["forecastDaily"]["temperature"]["value"][0] = item
    data = parse_weather(payload)
    assert data.temperature == expected.temperature
    assert data.hourly == expected.hourly
    assert len(data.daily) == daily_count
    assert data.daily[-14:] == expected.daily[1:]
    assert len(data.twice_daily) == 28 + len(periods)
    assert [period.is_daytime for period in data.twice_daily[: len(periods)]] == periods
    assert data.twice_daily[len(periods) :] == expected.twice_daily[2:]


def test_missing_daily_low(payload: dict[str, Any]) -> None:
    """Keep the daily high without inventing a missing low."""
    expected = parse_weather(payload)
    del payload["forecastDaily"]["temperature"]["value"][0]["to"]
    data = parse_weather(payload)
    assert data.daily[0] == replace(expected.daily[0], low=None)


@pytest.mark.parametrize(
    ("section", "key", "empty_forecasts", "unaffected"),
    [
        pytest.param(
            "forecastDaily",
            "temperature",
            ("daily", "twice_daily"),
            "hourly",
            id="daily-temperature",
        ),
        pytest.param(
            "forecastDaily",
            "sunRiseSet",
            ("daily", "twice_daily"),
            "temperature",
            id="sun-times",
        ),
        pytest.param(
            "forecastHourly",
            "temperature",
            ("hourly",),
            "daily",
            id="hourly-temperature",
        ),
    ],
)
@pytest.mark.parametrize(
    "series",
    [
        pytest.param(None, id="null-block"),
        pytest.param([], id="invalid-block"),
        pytest.param({"value": None}, id="null-array"),
        pytest.param({"value": "bad"}, id="invalid-array"),
    ],
)
def test_malformed_optional_series(
    payload: dict[str, Any],
    section: str,
    key: str,
    empty_forecasts: tuple[str, ...],
    unaffected: str,
    series: object,
) -> None:
    """Drop only forecasts that depend on a malformed optional series."""
    expected = parse_weather(payload)
    payload[section][key] = series
    data = parse_weather(payload)
    assert data.temperature == expected.temperature
    assert getattr(data, unaffected) == getattr(expected, unaffected)
    for forecast in empty_forecasts:
        assert getattr(data, forecast) == ()


@pytest.mark.parametrize(
    "series",
    [
        pytest.param(None, id="null-block"),
        pytest.param([], id="invalid-block"),
        pytest.param(
            {"pubTime": "2026-09-08T13:00:00+08:00", "value": None}, id="null-array"
        ),
        pytest.param(
            {"pubTime": "2026-09-08T13:00:00+08:00", "value": "bad"}, id="invalid-array"
        ),
    ],
)
def test_malformed_hourly_conditions(payload: dict[str, Any], series: object) -> None:
    """Retain hourly temperatures when the optional condition series is invalid."""
    expected = parse_weather(payload)
    payload["forecastHourly"]["weather"] = series
    assert parse_weather(payload) == replace(
        expected,
        hourly=tuple(replace(item, condition=None) for item in expected.hourly),
    )


@pytest.mark.parametrize(
    "timestamp_fields",
    [
        pytest.param({}, id="missing"),
        pytest.param({"pubTime": None}, id="null"),
        pytest.param({"pubTime": "bad"}, id="malformed"),
        pytest.param({"pubTime": "2026-09-08T13:00:00"}, id="missing-timezone"),
    ],
)
def test_invalid_hourly_timestamp(
    payload: dict[str, Any], timestamp_fields: dict[str, str | None]
) -> None:
    """An unusable hourly timestamp must not discard other weather data."""
    expected = replace(parse_weather(payload), hourly=())
    temperatures = payload["forecastHourly"]["temperature"]
    del temperatures["pubTime"]
    temperatures.update(timestamp_fields)
    assert parse_weather(payload) == expected


def test_clear_without_sun_times(payload: dict[str, Any]) -> None:
    """Test clear without sun times."""
    payload["current"]["weather"] = "0"
    payload["current"]["pubTime"] = "2026-09-07T12:00:00+08:00"
    assert parse_weather(payload).condition == "sunny"


@pytest.mark.parametrize(
    ("sun_fields", "missing_period", "daily_start"),
    [
        pytest.param({"to": "2026-09-08T18:36:00+08:00"}, 0, 1, id="missing-sunrise"),
        pytest.param(
            {"from": None, "to": "2026-09-08T18:36:00+08:00"}, 0, 1, id="null-sunrise"
        ),
        pytest.param(
            {"from": "bad", "to": "2026-09-08T18:36:00+08:00"},
            0,
            1,
            id="invalid-sunrise",
        ),
        pytest.param({"from": "2026-09-08T05:48:00+08:00"}, 1, 0, id="missing-sunset"),
        pytest.param(
            {"from": "2026-09-08T05:48:00+08:00", "to": None}, 1, 0, id="null-sunset"
        ),
        pytest.param(
            {"from": "2026-09-08T05:48:00+08:00", "to": "bad"},
            1,
            0,
            id="invalid-sunset",
        ),
    ],
)
def test_independent_forecast_solar_times(
    payload: dict[str, Any],
    sun_fields: dict[str, str | None],
    missing_period: int,
    daily_start: int,
) -> None:
    """An invalid solar time must not remove the other valid forecast period."""
    expected = parse_weather(payload)
    payload["forecastDaily"]["sunRiseSet"]["value"][0] = sun_fields
    data = parse_weather(payload)
    assert data.temperature == expected.temperature
    assert data.daily == expected.daily[daily_start:]
    assert data.twice_daily == (
        expected.twice_daily[:missing_period]
        + expected.twice_daily[missing_period + 1 :]
    )
    assert len(data.hourly) == len(expected.hourly)


def test_missing_daily_high_retains_night(payload: dict[str, Any]) -> None:
    """Test missing daily high retains night."""
    payload["forecastDaily"]["temperature"]["value"][0]["from"] = None
    data = parse_weather(payload)
    assert len(data.daily) == 14
    assert len(data.twice_daily) == 29
    assert data.twice_daily[0].is_daytime is False
    payload["forecastDaily"]["sunRiseSet"]["value"][0] = {"from": "bad", "to": None}
    payload["current"]["weather"] = "0"
    data = parse_weather(payload)
    assert len(data.twice_daily) == 28
    assert data.condition == "sunny"
