"""Test adding external statistics from Tibber."""
from unittest.mock import AsyncMock

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.tibber.sensor import TibberDataCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .test_common import CONSUMPTION_DATA_1, PRODUCTION_DATA_1, mock_get_homes

from tests.components.recorder.common import async_wait_recording_done


async def test_async_setup_entry(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test setup Tibber."""
    tibber_connection = AsyncMock()
    tibber_connection.name = "tibber"
    tibber_connection.fetch_consumption_data_active_homes.return_value = None
    tibber_connection.fetch_production_data_active_homes.return_value = None
    tibber_connection.get_homes = mock_get_homes

    coordinator = TibberDataCoordinator(hass, tibber_connection)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    for statistic_id, data, key in (
        ("tibber:energy_consumption_home_id", CONSUMPTION_DATA_1, "consumption"),
        ("tibber:energy_totalcost_home_id", CONSUMPTION_DATA_1, "totalCost"),
        ("tibber:energy_production_home_id", PRODUCTION_DATA_1, "production"),
        ("tibber:energy_profit_home_id", PRODUCTION_DATA_1, "profit"),
    ):
        stats = await hass.async_add_executor_job(
            statistics_during_period,
            hass,
            dt_util.parse_datetime(data[0]["from"]),
            None,
            [statistic_id],
            "hour",
            None,
            {"start", "state", "mean", "min", "max", "last_reset", "sum"},
        )

        assert len(stats) == 1
        assert len(stats[statistic_id]) == 3
        _sum = 0
        for k, stat in enumerate(stats[statistic_id]):
            assert stat["start"] == dt_util.parse_datetime(data[k]["from"]).timestamp()
            assert stat["state"] == data[k][key]
            assert stat["mean"] is None
            assert stat["min"] is None
            assert stat["max"] is None
            assert stat["last_reset"] is None

            _sum += data[k][key]
            assert stat["sum"] == _sum
