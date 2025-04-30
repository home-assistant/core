"""Test adding external statistics from Mill."""

from unittest.mock import AsyncMock

from mill import Heater, Mill, Sensor

from homeassistant.components.mill.const import DOMAIN
from homeassistant.components.mill.coordinator import MillHistoricDataUpdateCoordinator
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.components.recorder.common import async_wait_recording_done


async def test_mill_historic_data(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test historic data from Mill."""

    data = {
        dt_util.parse_datetime("2024-12-03T00:00:00+01:00"): 2,
        dt_util.parse_datetime("2024-12-03T01:00:00+01:00"): 3,
        dt_util.parse_datetime("2024-12-03T02:00:00+01:00"): 4,
    }

    mill_data_connection = Mill("", "", websession=AsyncMock())
    mill_data_connection.fetch_heater_and_sensor_data = AsyncMock(return_value=None)
    mill_data_connection.devices = {"dev_id": Heater(name="heater_name")}
    mill_data_connection.fetch_historic_energy_usage = AsyncMock(return_value=data)

    statistic_id = f"{DOMAIN}:energy_dev_id"

    coordinator = MillHistoricDataUpdateCoordinator(
        hass, mill_data_connection=mill_data_connection
    )
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        next(iter(data)),
        None,
        {statistic_id},
        "hour",
        None,
        {"start", "state", "mean", "min", "max", "last_reset", "sum"},
    )

    assert len(stats) == 1
    assert len(stats[statistic_id]) == 3
    _sum = 0
    for stat in stats[statistic_id]:
        start = dt_util.utc_from_timestamp(stat["start"])
        assert start in data
        assert stat["state"] == data[start]
        assert stat["last_reset"] is None

        _sum += data[start]
        assert stat["sum"] == _sum

    data2 = {
        dt_util.parse_datetime("2024-12-03T02:00:00+01:00"): 4.5,
        dt_util.parse_datetime("2024-12-03T03:00:00+01:00"): 5,
        dt_util.parse_datetime("2024-12-03T04:00:00+01:00"): 6,
        dt_util.parse_datetime("2024-12-03T05:00:00+01:00"): 7,
    }
    mill_data_connection.fetch_historic_energy_usage = AsyncMock(return_value=data2)
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        next(iter(data)),
        None,
        {statistic_id},
        "hour",
        None,
        {"start", "state", "mean", "min", "max", "last_reset", "sum"},
    )
    assert len(stats) == 1
    assert len(stats[statistic_id]) == 6
    _sum = 0
    for stat in stats[statistic_id]:
        start = dt_util.utc_from_timestamp(stat["start"])
        val = data2.get(start) if start in data2 else data.get(start)
        assert val is not None
        assert stat["state"] == val
        assert stat["last_reset"] is None

        _sum += val
        assert stat["sum"] == _sum


async def test_mill_historic_data_no_heater(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test historic data from Mill."""

    data = {
        dt_util.parse_datetime("2024-12-03T00:00:00+01:00"): 2,
        dt_util.parse_datetime("2024-12-03T01:00:00+01:00"): 3,
        dt_util.parse_datetime("2024-12-03T02:00:00+01:00"): 4,
    }

    mill_data_connection = Mill("", "", websession=AsyncMock())
    mill_data_connection.fetch_heater_and_sensor_data = AsyncMock(return_value=None)
    mill_data_connection.devices = {"dev_id": Sensor(name="sensor_name")}
    mill_data_connection.fetch_historic_energy_usage = AsyncMock(return_value=data)

    statistic_id = f"{DOMAIN}:energy_dev_id"

    coordinator = MillHistoricDataUpdateCoordinator(
        hass, mill_data_connection=mill_data_connection
    )
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        next(iter(data)),
        None,
        {statistic_id},
        "hour",
        None,
        {"start", "state", "mean", "min", "max", "last_reset", "sum"},
    )

    assert len(stats) == 0


async def test_mill_historic_data_no_data(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test historic data from Mill."""

    data = {
        dt_util.parse_datetime("2024-12-03T00:00:00+01:00"): 2,
        dt_util.parse_datetime("2024-12-03T01:00:00+01:00"): 3,
        dt_util.parse_datetime("2024-12-03T02:00:00+01:00"): 4,
    }

    mill_data_connection = Mill("", "", websession=AsyncMock())
    mill_data_connection.fetch_heater_and_sensor_data = AsyncMock(return_value=None)
    mill_data_connection.devices = {"dev_id": Heater(name="heater_name")}
    mill_data_connection.fetch_historic_energy_usage = AsyncMock(return_value=data)

    coordinator = MillHistoricDataUpdateCoordinator(
        hass, mill_data_connection=mill_data_connection
    )
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)

    statistic_id = f"{DOMAIN}:energy_dev_id"

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        next(iter(data)),
        None,
        {statistic_id},
        "hour",
        None,
        {"start", "state", "mean", "min", "max", "last_reset", "sum"},
    )
    assert len(stats) == 1
    assert len(stats[statistic_id]) == 3

    mill_data_connection.fetch_historic_energy_usage = AsyncMock(return_value=None)

    coordinator = MillHistoricDataUpdateCoordinator(
        hass, mill_data_connection=mill_data_connection
    )
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        next(iter(data)),
        None,
        {statistic_id},
        "hour",
        None,
        {"start", "state", "mean", "min", "max", "last_reset", "sum"},
    )

    assert len(stats) == 1
    assert len(stats[statistic_id]) == 3


async def test_mill_historic_data_invalid_data(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test historic data from Mill."""

    data = {
        dt_util.parse_datetime("2024-12-03T00:00:00+01:00"): None,
        dt_util.parse_datetime("2024-12-03T01:00:00+01:00"): 3,
        dt_util.parse_datetime("3024-12-03T02:00:00+01:00"): 4,
    }

    mill_data_connection = Mill("", "", websession=AsyncMock())
    mill_data_connection.fetch_heater_and_sensor_data = AsyncMock(return_value=None)
    mill_data_connection.devices = {"dev_id": Heater(name="heater_name")}
    mill_data_connection.fetch_historic_energy_usage = AsyncMock(return_value=data)

    statistic_id = f"{DOMAIN}:energy_dev_id"

    coordinator = MillHistoricDataUpdateCoordinator(
        hass, mill_data_connection=mill_data_connection
    )
    await coordinator._async_update_data()
    await async_wait_recording_done(hass)
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        next(iter(data)),
        None,
        {statistic_id},
        "hour",
        None,
        {"start", "state", "mean", "min", "max", "last_reset", "sum"},
    )

    assert len(stats) == 1
    assert len(stats[statistic_id]) == 1
