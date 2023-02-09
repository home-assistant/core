"""Test adding external statistics from southern_company."""

from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.southern_company import DOMAIN
from homeassistant.core import HomeAssistant

from tests.components.recorder.common import async_wait_recording_done
from tests.components.southern_company import HOURLY_DATA, async_init_integration


async def test_async_setup_entry(recorder_mock, hass: HomeAssistant):
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
        assert stat["start"] == hourly_data[k].time
        assert stat["state"] == hourly_data[k].usage
        assert stat["mean"] is None
        assert stat["min"] is None
        assert stat["max"] is None
        assert stat["last_reset"] is None

        _sum += hourly_data[k].cost
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
        assert stat["start"] == hourly_data[k].time
        assert stat["state"] == hourly_data[k].cost
        assert stat["mean"] is None
        assert stat["min"] is None
        assert stat["max"] is None
        assert stat["last_reset"] is None

        _sum += hourly_data[k].cost
        assert stat["sum"] == _sum
