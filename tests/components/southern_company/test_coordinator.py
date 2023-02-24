"""Test adding external statistics from southern_company."""

from datetime import timedelta

import pytest

from homeassistant.components.recorder.core import Recorder
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.southern_company import DOMAIN
from homeassistant.components.southern_company.coordinator import (
    SouthernCompanyCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt

from . import HOURLY_DATA, HOURLY_DATA_MISSING, MockedApi, async_init_integration

from tests.common import async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def test_statistic_insert(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test setup southern_company."""
    await async_init_integration(hass)
    await async_wait_recording_done(hass)
    cost_statistic_id = f"{DOMAIN}:energy_cost_1"
    usage_statistic_id = f"{DOMAIN}:energy_usage_1"
    hourly_data = HOURLY_DATA
    usage_stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        hourly_data[0].time,
        None,
        [usage_statistic_id],
        "hour",
        None,
        {"start", "state", "mean", "min", "max", "last_reset", "sum"},
    )

    assert len(usage_stats) == 1
    assert len(usage_stats[usage_statistic_id]) == 2
    _sum = 0
    for k, stat in enumerate(usage_stats[usage_statistic_id]):
        assert stat["start"] == hourly_data[k].time.timestamp()
        assert stat["state"] == hourly_data[k].usage
        assert stat["mean"] is None
        assert stat["min"] is None
        assert stat["max"] is None
        assert stat["last_reset"] is None

        _sum += hourly_data[k].usage
        assert stat["sum"] == _sum

    cost_stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        hourly_data[0].time,
        None,
        [cost_statistic_id],
        "hour",
        None,
        {"start", "state", "mean", "min", "max", "last_reset", "sum"},
    )

    assert len(cost_stats) == 1
    assert len(cost_stats[cost_statistic_id]) == 2
    _sum = 0
    for k, stat in enumerate(cost_stats[cost_statistic_id]):
        assert stat["start"] == hourly_data[k].time.timestamp()
        assert stat["state"] == hourly_data[k].cost
        assert stat["mean"] is None
        assert stat["min"] is None
        assert stat["max"] is None
        assert stat["last_reset"] is None

        _sum += hourly_data[k].cost
        assert stat["sum"] == _sum
    await hass.async_block_till_done()
    # Check that everything works correctly when last_stats does exist.
    async_fire_time_changed(hass, dt.utcnow() + timedelta(minutes=61))
    await hass.async_block_till_done()


async def test_update_coordinator_no_jwt(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Ensure if a coordinator update happens, and there is no jwt, then we report update failed."""
    api_mock = MockedApi(None, [])
    coordinator = SouthernCompanyCoordinator(hass, api_mock)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_statistics_no_jwt(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Ensure if a statistic update happens, and there is no jwt, then we report update failed."""
    api_mock = MockedApi(None, [])
    coordinator = SouthernCompanyCoordinator(hass, api_mock)
    with pytest.raises(UpdateFailed):
        await coordinator._insert_statistics()


async def test_statistics_missing_data(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Ensure that if a piece of data is missing, i.e. cost or usage, we should not add that to the statistics."""
    await async_init_integration(hass, hourly_data=HOURLY_DATA_MISSING)
    await async_wait_recording_done(hass)
    cost_statistic_id = f"{DOMAIN}:energy_cost_1"
    usage_statistic_id = f"{DOMAIN}:energy_usage_1"
    hourly_data = HOURLY_DATA
    usage_stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        hourly_data[0].time,
        None,
        [usage_statistic_id],
        "hour",
        None,
        {"start", "state", "mean", "min", "max", "last_reset", "sum"},
    )

    assert len(usage_stats) == 1
    assert len(usage_stats[usage_statistic_id]) == 2
    _sum = 0
    for k, stat in enumerate(usage_stats[usage_statistic_id]):
        assert stat["start"] == hourly_data[k].time.timestamp()
        assert stat["state"] == hourly_data[k].usage
        assert stat["mean"] is None
        assert stat["min"] is None
        assert stat["max"] is None
        assert stat["last_reset"] is None

        _sum += hourly_data[k].usage
        assert stat["sum"] == _sum

    cost_stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        hourly_data[0].time,
        None,
        [cost_statistic_id],
        "hour",
        None,
        {"start", "state", "mean", "min", "max", "last_reset", "sum"},
    )

    assert len(cost_stats) == 1
    assert len(cost_stats[cost_statistic_id]) == 2
    _sum = 0
    for k, stat in enumerate(cost_stats[cost_statistic_id]):
        assert stat["start"] == hourly_data[k].time.timestamp()
        assert stat["state"] == hourly_data[k].cost
        assert stat["mean"] is None
        assert stat["min"] is None
        assert stat["max"] is None
        assert stat["last_reset"] is None

        _sum += hourly_data[k].cost
        assert stat["sum"] == _sum
    await hass.async_block_till_done()
