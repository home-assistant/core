"""Test Suez_water statistics."""

from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.suez_water.const import DATA_REFRESH_INTERVAL
from homeassistant.components.suez_water.coordinator import (
    CONF_COUNTER_ID,
    DOMAIN,
    DayDataResult,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


@pytest.mark.parametrize(
    "statistic", [("water_cost_statistics"), ("water_consumption_statistics")]
)
async def test_statistics(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    recorder_mock: Recorder,
    freezer: FrozenDateTimeFactory,
    statistic: str,
) -> None:
    """Test that suez_water statisticts are working."""
    nb_samples = 120

    start = datetime.now().replace(hour=2)
    freezer.move_to(start)

    origin = datetime.combine(
        start.date(), time(0, 0, 0, 0), ZoneInfo("Europe/Paris")
    ) - timedelta(days=nb_samples)
    result = [
        DayDataResult((origin + timedelta(days=d)).date(), 500, 500 * (d + 1))
        for d in range(nb_samples)
    ]
    suez_client.fetch_all_daily_data.return_value = result

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Init data retrieved
    await _test_for_data(
        hass,
        suez_client,
        statistic,
        origin,
        mock_config_entry.data[CONF_COUNTER_ID],
        nb_samples,
        1,
    )

    # No new data retrieved
    suez_client.fetch_all_daily_data.return_value = []
    freezer.tick(DATA_REFRESH_INTERVAL)
    async_fire_time_changed(hass)

    await _test_for_data(
        hass,
        suez_client,
        statistic,
        origin,
        mock_config_entry.data[CONF_COUNTER_ID],
        nb_samples,
        2,
    )
    # Old data retrieved
    suez_client.fetch_all_daily_data.return_value = [
        DayDataResult(origin.date() - timedelta(days=1), 500, 500 * (121 + 1))
    ]
    freezer.tick(DATA_REFRESH_INTERVAL)
    async_fire_time_changed(hass)

    await _test_for_data(
        hass,
        suez_client,
        statistic,
        origin,
        mock_config_entry.data[CONF_COUNTER_ID],
        nb_samples,
        3,
    )

    # New daily data retrieved
    suez_client.fetch_all_daily_data.return_value = [
        DayDataResult(datetime.now().date(), 500, 500 * (121 + 1))
    ]
    freezer.tick(DATA_REFRESH_INTERVAL)
    async_fire_time_changed(hass)

    await _test_for_data(
        hass,
        suez_client,
        statistic,
        origin,
        mock_config_entry.data[CONF_COUNTER_ID],
        nb_samples,
        4,
        1,
    )


async def _test_for_data(
    hass: HomeAssistant,
    suez_client: AsyncMock,
    statistic: str,
    origin: datetime,
    counter_id: str,
    nb_samples: int,
    nb_calls: int,
    extra_samples: int = 0,
) -> None:
    await hass.async_block_till_done(True)
    await async_wait_recording_done(hass)

    assert suez_client.fetch_all_daily_data.call_count == nb_calls
    statistic_id = f"{DOMAIN}:{counter_id}_{statistic}"
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        origin - timedelta(days=1),
        None,
        [statistic_id],
        "hour",
        None,
        {"start", "state", "mean", "min", "max", "last_reset", "sum"},
    )

    assert stats.get(statistic_id) is not None
    assert len(stats[statistic_id]) == nb_samples + extra_samples
    _sum = 0
    for _k, stat in enumerate(stats[statistic_id]):
        value = 500
        if statistic == "water_cost_statistics":
            value = (500 / 1000) * 4.74

        assert stat["state"] == value
        assert stat["last_reset"] is None

        _sum += value
        assert stat["sum"] == _sum
        assert stat.get("max") is None
        assert stat.get("min") is None
        assert stat.get("mean") is None
        assert stat.get("last_reset") is None
