"""Test Home Assistant display policies over the library's typed data."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion
from xiaomi_weather import parse_weather

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

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
    client: AsyncMock,
    entry: MockConfigEntry,
    payload: dict[str, Any],
    time: str,
    solar_times: bool,
    expected: str,
) -> None:
    """Use the weather location's day boundaries, independent of the HA timezone."""
    payload["current"].update(weather="0", pubTime=time)
    payload["forecastDaily"]["sunRiseSet"]["status"] = int(not solar_times)
    client.return_value = parse_weather(payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("weather.beijing")
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
    client: AsyncMock,
    entry: MockConfigEntry,
    payload: dict[str, Any],
    snapshot: SnapshotAssertion,
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
    client.return_value = parse_weather(payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("weather.beijing")
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes == snapshot


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({}, id="complete"),
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
    client: AsyncMock,
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
    client.return_value = parse_weather(payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": "weather.beijing", "type": forecast_type},
            blocking=True,
            return_response=True,
        )
        == snapshot
    )
    client.assert_awaited_once_with("101010100", 39.9042, 116.4074)


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
    client: AsyncMock,
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
    client.return_value = parse_weather(payload)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": "weather.beijing", "type": "hourly"},
            blocking=True,
            return_response=True,
        )
        == snapshot
    )
    client.assert_awaited_once()
