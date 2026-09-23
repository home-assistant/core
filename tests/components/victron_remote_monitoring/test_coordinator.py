"""Tests for Victron Remote Monitoring forecast day boundaries."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
import pytest
from victron_vrm.models.aggregations import ForecastAggregations

from homeassistant.components.victron_remote_monitoring.coordinator import get_forecast
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("now_utc", "today_start_utc", "tomorrow_start_utc", "expected_left"),
    [
        pytest.param(
            "2026-07-10T21:00:00+00:00",
            "2026-07-09T22:00:00+00:00",
            "2026-07-10T22:00:00+00:00",
            3,
            id="summer-before-midnight",
        ),
        pytest.param(
            "2026-07-10T22:00:00+00:00",
            "2026-07-10T22:00:00+00:00",
            "2026-07-11T22:00:00+00:00",
            5,
            id="summer-after-midnight",
        ),
        pytest.param(
            "2026-01-10T22:00:00+00:00",
            "2026-01-09T23:00:00+00:00",
            "2026-01-10T23:00:00+00:00",
            3,
            id="winter-before-midnight",
        ),
        pytest.param(
            "2026-01-10T23:00:00+00:00",
            "2026-01-10T23:00:00+00:00",
            "2026-01-11T23:00:00+00:00",
            5,
            id="winter-after-midnight",
        ),
    ],
)
async def test_forecast_uses_local_midnight(
    hass: HomeAssistant,
    mock_vrm_client: MagicMock,
    now_utc: str,
    today_start_utc: str,
    tomorrow_start_utc: str,
    expected_left: int,
) -> None:
    """Daily totals and remaining forecast switch at local midnight."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    now = datetime.fromisoformat(now_utc)
    today_start = datetime.fromisoformat(today_start_utc)
    tomorrow_start = datetime.fromisoformat(tomorrow_start_utc)
    records = [
        (int((today_start - timedelta(hours=1)).timestamp()), 1),
        (int(today_start.timestamp()), 2),
        (int((tomorrow_start - timedelta(hours=1)).timestamp()), 3),
        (int(tomorrow_start.timestamp()), 4),
        (int((tomorrow_start + timedelta(hours=1)).timestamp()), 5),
    ]
    aggregation = ForecastAggregations(
        start=records[0][0],
        end=records[-1][0],
        site_id=123456,
        records=records,
        custom_dt_now=lambda: now,
        time_zone=ZoneInfo("Europe/Berlin"),
    )
    mock_vrm_client.installations.stats.return_value = {
        "solar_yield": aggregation,
        "consumption": aggregation,
    }

    with patch(
        "homeassistant.components.victron_remote_monitoring.coordinator.dt_util.now",
        return_value=now.astimezone(ZoneInfo("Europe/Berlin")),
    ):
        store = await get_forecast(mock_vrm_client, 123456)

    assert store.solar is not None
    assert store.consumption is not None
    for forecast in (store.solar, store.consumption):
        assert forecast.yesterday_total == 1
        assert forecast.today_total == 5
        assert forecast.today_left_total == expected_left
        assert forecast.tomorrow_total == 9
        assert forecast.today_peak_time == tomorrow_start - timedelta(hours=1)
        assert forecast.today_range == (
            int(today_start.timestamp()),
            int(tomorrow_start.timestamp()),
        )
        assert forecast.today_left_range == (
            int(now.timestamp()),
            int(tomorrow_start.timestamp()),
        )


@pytest.mark.parametrize(
    (
        "now_utc",
        "today_start_utc",
        "tomorrow_start_utc",
        "query_start_utc",
        "query_end_utc",
        "day_hours",
    ),
    [
        pytest.param(
            "2026-03-29T12:00:00+00:00",
            "2026-03-28T23:00:00+00:00",
            "2026-03-29T22:00:00+00:00",
            "2026-03-27T23:00:00+00:00",
            "2026-04-03T22:00:00+00:00",
            23,
            id="spring-forward",
        ),
        pytest.param(
            "2026-10-25T12:00:00+00:00",
            "2026-10-24T22:00:00+00:00",
            "2026-10-25T23:00:00+00:00",
            "2026-10-23T22:00:00+00:00",
            "2026-10-30T23:00:00+00:00",
            25,
            id="fall-back",
        ),
    ],
)
async def test_forecast_dst_day_range(
    hass: HomeAssistant,
    mock_vrm_client: MagicMock,
    now_utc: str,
    today_start_utc: str,
    tomorrow_start_utc: str,
    query_start_utc: str,
    query_end_utc: str,
    day_hours: int,
) -> None:
    """The day range follows the actual length of a local DST day."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    now = datetime.fromisoformat(now_utc)
    today_start = datetime.fromisoformat(today_start_utc)
    tomorrow_start = datetime.fromisoformat(tomorrow_start_utc)
    records = [
        (int((today_start - timedelta(hours=1)).timestamp()), 1),
        (int(today_start.timestamp()), 2),
        (int((tomorrow_start - timedelta(hours=1)).timestamp()), 3),
        (int(tomorrow_start.timestamp()), 4),
    ]
    aggregation = ForecastAggregations(
        start=records[0][0],
        end=records[-1][0],
        site_id=123456,
        records=records,
        custom_dt_now=lambda: now,
        time_zone=ZoneInfo("Europe/Berlin"),
    )
    mock_vrm_client.installations.stats.return_value = {
        "solar_yield": aggregation,
        "consumption": aggregation,
    }

    with patch(
        "homeassistant.components.victron_remote_monitoring.coordinator.dt_util.now",
        return_value=now.astimezone(ZoneInfo("Europe/Berlin")),
    ):
        store = await get_forecast(mock_vrm_client, 123456)

    assert store.consumption is not None
    assert store.consumption.today_range == (
        int(today_start.timestamp()),
        int(tomorrow_start.timestamp()),
    )
    assert store.consumption.today_total == 5
    assert mock_vrm_client.installations.stats.call_args.kwargs[
        "time_zone"
    ] == ZoneInfo("Europe/Berlin")
    assert (store.consumption.today_range[1] - store.consumption.today_range[0]) == (
        day_hours * 3600
    )
    mock_vrm_client.installations.stats.assert_awaited_once()
    assert mock_vrm_client.installations.stats.call_args.kwargs["start"] == int(
        datetime.fromisoformat(query_start_utc).timestamp()
    )
    assert mock_vrm_client.installations.stats.call_args.kwargs["end"] == int(
        datetime.fromisoformat(query_end_utc).timestamp()
    )


async def test_hourly_forecasts_during_fall_back(
    hass: HomeAssistant,
    mock_vrm_client: MagicMock,
) -> None:
    """The next hour follows elapsed time during the repeated local hour."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    now = datetime.fromisoformat("2026-10-25T00:30:00+00:00")
    records = [
        (int(datetime.fromisoformat(timestamp).timestamp()), value)
        for timestamp, value in (
            ("2026-10-25T00:00:00+00:00", 10),
            ("2026-10-25T01:00:00+00:00", 20),
            ("2026-10-25T02:00:00+00:00", 30),
        )
    ]
    aggregation = ForecastAggregations(
        start=records[0][0],
        end=records[-1][0],
        site_id=123456,
        records=records,
        custom_dt_now=lambda: now,
        time_zone=ZoneInfo("Europe/Berlin"),
    )
    mock_vrm_client.installations.stats.return_value = {
        "solar_yield": aggregation,
        "consumption": aggregation,
    }

    with patch(
        "homeassistant.components.victron_remote_monitoring.coordinator.dt_util.now",
        return_value=now.astimezone(ZoneInfo("Europe/Berlin")),
    ):
        store = await get_forecast(mock_vrm_client, 123456)

    assert store.solar is not None
    assert store.solar.current_hour_total == 10
    assert store.solar.next_hour_total == 20
    assert store.solar.next_hour_timestamp == (records[1][0], records[2][0])
    assert store.solar.today_left_range[1] == int(
        datetime.fromisoformat("2026-10-25T23:00:00+00:00").timestamp()
    )


@pytest.mark.parametrize(
    ("before_midnight", "after_midnight"),
    [
        pytest.param(
            "2026-07-10T21:59:00+00:00",
            "2026-07-10T22:00:01+00:00",
            id="summer",
        ),
        pytest.param(
            "2026-01-10T22:59:00+00:00",
            "2026-01-10T23:00:01+00:00",
            id="winter",
        ),
    ],
)
async def test_refreshes_at_local_midnight(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vrm_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    before_midnight: str,
    after_midnight: str,
) -> None:
    """Request new forecast data when the local day changes."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(before_midnight)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_vrm_client.installations.stats.await_count == 1

    freezer.move_to(after_midnight)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_vrm_client.installations.stats.await_count == 2


@pytest.mark.parametrize(
    ("missing_key", "missing_field", "present_field"),
    [
        pytest.param("solar_yield", "solar", "consumption", id="missing-solar"),
        pytest.param("consumption", "consumption", "solar", id="missing-consumption"),
    ],
)
async def test_missing_forecast_series(
    mock_vrm_client: MagicMock,
    missing_key: str,
    missing_field: str,
    present_field: str,
) -> None:
    """Keep a missing VRM forecast series unavailable."""
    mock_vrm_client.installations.stats.return_value[missing_key] = None

    store = await get_forecast(mock_vrm_client, 123456)

    assert getattr(store, missing_field) is None
    assert getattr(store, present_field) is not None
