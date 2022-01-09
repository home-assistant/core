"""Test adding external statistics from Tibber."""
from unittest.mock import AsyncMock

from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.tibber.sensor import TibberDataCoordinator
from homeassistant.util import dt as dt_util

from tests.common import async_init_recorder_component
from tests.components.recorder.common import async_wait_recording_done_without_instance

_CONSUMPTION_DATA_1 = [
    {
        "from": "2022-01-03T00:00:00.000+01:00",
        "totalCost": 1.1,
        "consumption": 2.1,
    },
    {
        "from": "2022-01-03T01:00:00.000+01:00",
        "totalCost": 1.2,
        "consumption": 2.2,
    },
    {
        "from": "2022-01-03T02:00:00.000+01:00",
        "totalCost": 1.3,
        "consumption": 2.3,
    },
]


async def test_async_setup_entry(hass):
    """Test setup Tibber."""
    await async_init_recorder_component(hass)

    def _get_homes():
        tibber_home = AsyncMock()
        tibber_home.name = "Name"
        tibber_home.home_id = "home_id"
        tibber_home.currency = "NOK"
        tibber_home.get_historic_data.return_value = _CONSUMPTION_DATA_1
        return [tibber_home]

    tibber_connection = AsyncMock()
    tibber_connection.name = "tibber"
    tibber_connection.fetch_consumption_data_active_homes.return_value = None
    tibber_connection.get_homes = _get_homes

    coordinator = TibberDataCoordinator(hass, tibber_connection)
    await coordinator._async_update_data()
    await async_wait_recording_done_without_instance(hass)

    # Validate consumption
    statistic_id = "tibber:energy_consumption_home_id"

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.parse_datetime(_CONSUMPTION_DATA_1[0]["from"]),
        None,
        [statistic_id],
        "hour",
        True,
    )

    assert len(stats) == 1
    assert len(stats[statistic_id]) == 3
    _sum = 0
    for k, stat in enumerate(stats[statistic_id]):
        assert stat["start"] == dt_util.parse_datetime(_CONSUMPTION_DATA_1[k]["from"])
        assert stat["state"] == _CONSUMPTION_DATA_1[k]["consumption"]
        assert stat["mean"] is None
        assert stat["min"] is None
        assert stat["max"] is None
        assert stat["last_reset"] is None

        _sum += _CONSUMPTION_DATA_1[k]["consumption"]
        assert stat["sum"] == _sum

    # Validate cost
    statistic_id = "tibber:energy_totalcost_home_id"

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.parse_datetime(_CONSUMPTION_DATA_1[0]["from"]),
        None,
        [statistic_id],
        "hour",
        True,
    )

    assert len(stats) == 1
    assert len(stats[statistic_id]) == 3
    _sum = 0
    for k, stat in enumerate(stats[statistic_id]):
        assert stat["start"] == dt_util.parse_datetime(_CONSUMPTION_DATA_1[k]["from"])
        assert stat["state"] == _CONSUMPTION_DATA_1[k]["totalCost"]
        assert stat["mean"] is None
        assert stat["min"] is None
        assert stat["max"] is None
        assert stat["last_reset"] is None

        _sum += _CONSUMPTION_DATA_1[k]["totalCost"]
        assert stat["sum"] == _sum
