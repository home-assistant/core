"""Tests for the Victron Remote Monitoring forecast service."""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.victron_remote_monitoring.const import DOMAIN
from homeassistant.components.victron_remote_monitoring.services import (
    VictronRemoteMonitoringService,
    VictronRemoteMonitoringServiceArgument,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

_SOLAR_WH = {
    "2025-04-23T10:00:00+00:00": 5050.1,
    "2025-04-23T11:00:00+00:00": 5000.2,
    "2025-04-24T10:00:00+00:00": 2250.3,
    "2025-04-24T11:00:00+00:00": 2000.4,
    "2025-04-25T10:00:00+00:00": 1000.5,
    "2025-04-25T11:00:00+00:00": 500.6,
}
_SOLAR_TODAY = "sensor.victron_remote_monitoring_estimated_energy_production_today"
_CONSUMPTION_TODAY = (
    "sensor.victron_remote_monitoring_estimated_energy_consumption_today"
)


def _mark_consumption_false(stats: dict[str, Any]) -> None:
    """Replace the consumption aggregation with the API's false sentinel."""
    stats["consumption"] = False


def _drop_consumption(stats: dict[str, Any]) -> None:
    """Remove the consumption series from the stats payload."""
    del stats["consumption"]


@pytest.fixture
async def utc_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Load the entry with UTC selected before the forecast is fetched."""
    await hass.config.async_set_time_zone("UTC")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


async def _async_get_forecast(
    hass: HomeAssistant,
    entry_id: str,
    **extra: datetime,
) -> dict[str, Any]:
    """Call get_forecast and return its response."""
    response = await hass.services.async_call(
        DOMAIN,
        VictronRemoteMonitoringService.GET_FORECAST,
        {
            VictronRemoteMonitoringServiceArgument.CONFIG_ENTRY: entry_id,
            **extra,
        },
        blocking=True,
        return_response=True,
    )
    assert isinstance(response, dict)
    return response


async def test_get_forecast_returns_cached_watt_hours(
    hass: HomeAssistant,
    utc_entry: MockConfigEntry,
    mock_vrm_client: AsyncMock,
) -> None:
    """Return both hourly series from memory without another VRM request."""
    response = await _async_get_forecast(hass, utc_entry.entry_id)

    assert response == {"solar_wh": _SOLAR_WH, "consumption_wh": _SOLAR_WH}
    assert list(response["solar_wh"]) == list(_SOLAR_WH)
    assert all(isinstance(value, float) for value in response["solar_wh"].values())
    mock_vrm_client.installations.stats.assert_awaited_once()
    assert (
        mock_vrm_client.installations.stats.call_args.kwargs["return_aggregations"]
        is True
    )
    state = hass.states.get(_SOLAR_TODAY)
    assert state is not None
    assert state.state == "4.2507"
    assert "solar_wh" not in state.attributes
    assert "consumption_wh" not in state.attributes


@pytest.mark.parametrize(
    ("extra", "expected_keys"),
    [
        pytest.param(
            {
                VictronRemoteMonitoringServiceArgument.START: datetime.fromisoformat(
                    "2025-04-23T11:00:00+00:00"
                ),
                VictronRemoteMonitoringServiceArgument.END: datetime.fromisoformat(
                    "2025-04-25T10:00:00+00:00"
                ),
            },
            [
                "2025-04-23T11:00:00+00:00",
                "2025-04-24T10:00:00+00:00",
                "2025-04-24T11:00:00+00:00",
            ],
            id="half-open-range",
        ),
        pytest.param(
            {
                VictronRemoteMonitoringServiceArgument.START: datetime.fromisoformat(
                    "2025-04-24T11:00:00+00:00"
                ),
            },
            [
                "2025-04-24T11:00:00+00:00",
                "2025-04-25T10:00:00+00:00",
                "2025-04-25T11:00:00+00:00",
            ],
            id="start-only",
        ),
        pytest.param(
            {
                VictronRemoteMonitoringServiceArgument.END: datetime.fromisoformat(
                    "2025-04-24T10:00:00+00:00"
                ),
            },
            [
                "2025-04-23T10:00:00+00:00",
                "2025-04-23T11:00:00+00:00",
            ],
            id="end-only",
        ),
    ],
)
async def test_get_forecast_filters_series(
    hass: HomeAssistant,
    utc_entry: MockConfigEntry,
    extra: dict[str, datetime],
    expected_keys: list[str],
) -> None:
    """Keep hours at or after start and before end, and omit a missing bound."""
    response = await _async_get_forecast(hass, utc_entry.entry_id, **extra)

    assert list(response["solar_wh"]) == expected_keys
    assert response["solar_wh"] == {key: _SOLAR_WH[key] for key in expected_keys}
    assert response["consumption_wh"] == response["solar_wh"]


async def test_get_forecast_naive_bounds_use_default_timezone(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Interpret naive start and end in the Home Assistant default timezone."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await _async_get_forecast(
        hass,
        mock_config_entry.entry_id,
        **{
            VictronRemoteMonitoringServiceArgument.START: datetime(2025, 4, 23, 13, 0),
            VictronRemoteMonitoringServiceArgument.END: datetime(2025, 4, 24, 13, 0),
        },
    )

    assert response["solar_wh"] == {
        "2025-04-23T13:00:00+02:00": 5000.2,
        "2025-04-24T12:00:00+02:00": 2250.3,
    }
    assert response["consumption_wh"] == response["solar_wh"]


async def test_get_forecast_rejects_end_before_start(
    hass: HomeAssistant,
    utc_entry: MockConfigEntry,
) -> None:
    """Reject a range whose end is earlier than its start."""
    with pytest.raises(ServiceValidationError) as err:
        await _async_get_forecast(
            hass,
            utc_entry.entry_id,
            **{
                VictronRemoteMonitoringServiceArgument.START: datetime.fromisoformat(
                    "2025-04-25T11:00:00+00:00"
                ),
                VictronRemoteMonitoringServiceArgument.END: datetime.fromisoformat(
                    "2025-04-23T10:00:00+00:00"
                ),
            },
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "end_before_start"


async def test_get_forecast_allows_empty_half_open_range(
    hass: HomeAssistant,
    utc_entry: MockConfigEntry,
) -> None:
    """An end equal to the start is an empty range."""
    bound = datetime.fromisoformat("2025-04-24T10:00:00+00:00")

    response = await _async_get_forecast(
        hass,
        utc_entry.entry_id,
        **{
            VictronRemoteMonitoringServiceArgument.START: bound,
            VictronRemoteMonitoringServiceArgument.END: bound,
        },
    )

    assert response == {"solar_wh": {}, "consumption_wh": {}}


async def test_consumption_series_can_be_shorter(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vrm_client: AsyncMock,
) -> None:
    """Return only the hours present in each series."""
    await hass.config.async_set_time_zone("UTC")
    consumption = mock_vrm_client.installations.stats.return_value["consumption"]
    consumption.records = consumption.records[:-1]
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await _async_get_forecast(hass, mock_config_entry.entry_id)

    assert response["solar_wh"] == _SOLAR_WH
    assert response["consumption_wh"] == dict(tuple(_SOLAR_WH.items())[:-1])
    state = hass.states.get(_SOLAR_TODAY)
    assert state is not None
    assert state.state == "4.2507"


@pytest.mark.parametrize(
    "adjust_stats",
    [
        pytest.param(_mark_consumption_false, id="false"),
        pytest.param(_drop_consumption, id="missing"),
    ],
)
async def test_false_or_missing_consumption_keeps_solar(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vrm_client: AsyncMock,
    adjust_stats: Callable[[dict[str, Any]], None],
) -> None:
    """A false or missing consumption series does not fail the update."""
    await hass.config.async_set_time_zone("UTC")
    adjust_stats(mock_vrm_client.installations.stats.return_value)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_vrm_client.installations.stats.assert_awaited_once()
    response = await _async_get_forecast(hass, mock_config_entry.entry_id)

    assert response["solar_wh"] == _SOLAR_WH
    assert response["consumption_wh"] == {}
    solar_state = hass.states.get(_SOLAR_TODAY)
    consumption_state = hass.states.get(_CONSUMPTION_TODAY)
    assert solar_state is not None
    assert solar_state.state == "4.2507"
    assert consumption_state is not None
    assert consumption_state.state == STATE_UNKNOWN
