"""The test for the statistics sensor platform."""
from datetime import datetime, timedelta
from os import path
import statistics

import pytest

from homeassistant import config as hass_config
from homeassistant.components import recorder
from homeassistant.components.statistics.sensor import DOMAIN, StatisticsSensor
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_RELOAD,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.async_mock import patch
from tests.common import async_fire_time_changed, init_recorder_component
from tests.components.recorder.common import trigger_db_commit


@pytest.fixture(autouse=True)
def mock_legacy_time(legacy_patchable_time):
    """Make time patchable for all the tests."""
    yield


@pytest.fixture()
def stats():
    """Return common values and stats for all tests."""

    class Stats:
        def __init__(self):
            self.values = [17, 20, 15.2, 5, 3.8, 9.2, 6.7, 14, 6]
            self.count = len(self.values)
            self.min = min(self.values)
            self.max = max(self.values)
            self.total = sum(self.values)
            self.mean = round(sum(self.values) / len(self.values), 2)
            self.median = round(statistics.median(self.values), 2)
            self.deviation = round(statistics.stdev(self.values), 2)
            self.variance = round(statistics.variance(self.values), 2)
            self.change = round(self.values[-1] - self.values[0], 2)
            self.avg_change = round(self.change / (len(self.values) - 1), 2)
            self.change_rate = round(self.change / (60 * (self.count - 1)), 2)

    return Stats()


async def test_binary_sensor_source(hass):
    """Test if source is a sensor."""
    values = ["on", "off", "on", "off", "on", "off", "on"]
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "statistics",
                "name": "test",
                "entity_id": "binary_sensor.test_monitored",
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    for value in values:
        hass.states.async_set("binary_sensor.test_monitored", value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test")

    assert str(len(values)) == state.state


async def test_sensor_source(hass, stats):
    """Test if source is a sensor."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "statistics",
                "name": "test",
                "entity_id": "sensor.test_monitored",
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    for value in stats.values:
        hass.states.async_set(
            "sensor.test_monitored",
            value,
            {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test")

    assert str(stats.mean) == state.state
    assert stats.max == state.attributes.get("max_value")
    assert stats.min == state.attributes.get("min_value")
    assert stats.variance == state.attributes.get("variance")
    assert stats.median == state.attributes.get("median")
    assert stats.deviation == state.attributes.get("standard_deviation")
    assert stats.mean == state.attributes.get("mean")
    assert stats.count == state.attributes.get("count")
    assert stats.total == state.attributes.get("total")
    assert TEMP_CELSIUS == state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    assert stats.change == state.attributes.get("change")
    assert stats.avg_change == state.attributes.get("average_change")


async def test_sampling_size(hass, stats):
    """Test rotation."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "statistics",
                "name": "test",
                "entity_id": "sensor.test_monitored",
                "sampling_size": 5,
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    for value in stats.values:
        hass.states.async_set(
            "sensor.test_monitored", value, {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS}
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test")

    assert 3.8 == state.attributes.get("min_value")
    assert 14 == state.attributes.get("max_value")


async def test_sampling_size_1(hass, stats):
    """Test validity of stats requiring only one sample."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "statistics",
                "name": "test",
                "entity_id": "sensor.test_monitored",
                "sampling_size": 1,
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    for value in stats.values[-3:]:  # just the last 3 will do
        hass.states.async_set(
            "sensor.test_monitored", value, {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS}
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test")

    # require only one data point
    assert stats.values[-1] == state.attributes.get("min_value")
    assert stats.values[-1] == state.attributes.get("max_value")
    assert stats.values[-1] == state.attributes.get("mean")
    assert stats.values[-1] == state.attributes.get("median")
    assert stats.values[-1] == state.attributes.get("total")
    assert 0 == state.attributes.get("change")
    assert 0 == state.attributes.get("average_change")

    # require at least two data points
    assert STATE_UNKNOWN == state.attributes.get("variance")
    assert STATE_UNKNOWN == state.attributes.get("standard_deviation")


async def test_max_age(hass, stats):
    """Test value deprecation."""
    now = dt_util.utcnow()
    mock_data = {
        "return_time": datetime(now.year + 1, 8, 2, 12, 23, tzinfo=dt_util.UTC)
    }

    def mock_now():
        return mock_data["return_time"]

    with patch(
        "homeassistant.components.statistics.sensor.dt_util.utcnow", new=mock_now
    ):
        assert await async_setup_component(
            hass,
            "sensor",
            {
                "sensor": {
                    "platform": "statistics",
                    "name": "test",
                    "entity_id": "sensor.test_monitored",
                    "max_age": {"minutes": 3},
                }
            },
        )

        await hass.async_block_till_done()
        await hass.async_start()
        await hass.async_block_till_done()

        for value in stats.values:
            hass.states.async_set(
                "sensor.test_monitored",
                value,
                {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
            )
            await hass.async_block_till_done()
            # insert the next value one minute later
            mock_data["return_time"] += timedelta(minutes=1)

        state = hass.states.get("sensor.test")

    assert 6 == state.attributes.get("min_value")
    assert 14 == state.attributes.get("max_value")


async def test_max_age_without_sensor_change(hass, stats):
    """Test value deprecation."""
    now = dt_util.utcnow()
    mock_data = {
        "return_time": datetime(now.year + 1, 8, 2, 12, 23, tzinfo=dt_util.UTC)
    }

    def mock_now():
        return mock_data["return_time"]

    with patch(
        "homeassistant.components.statistics.sensor.dt_util.utcnow", new=mock_now
    ):
        assert await async_setup_component(
            hass,
            "sensor",
            {
                "sensor": {
                    "platform": "statistics",
                    "name": "test",
                    "entity_id": "sensor.test_monitored",
                    "max_age": {"minutes": 3},
                }
            },
        )

        await hass.async_block_till_done()
        await hass.async_start()
        await hass.async_block_till_done()

        for value in stats.values:
            hass.states.async_set(
                "sensor.test_monitored",
                value,
                {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
            )
            await hass.async_block_till_done()
            # insert the next value 30 seconds later
            mock_data["return_time"] += timedelta(seconds=30)

        state = hass.states.get("sensor.test")

        assert 3.8 == state.attributes.get("min_value")
        assert 15.2 == state.attributes.get("max_value")

        # wait for 3 minutes (max_age).
        mock_data["return_time"] += timedelta(minutes=3)
        async_fire_time_changed(hass, mock_data["return_time"])
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test")

        assert state.attributes.get("min_value") == STATE_UNKNOWN
        assert state.attributes.get("max_value") == STATE_UNKNOWN
        assert state.attributes.get("count") == 0


async def test_change_rate(hass, stats):
    """Test min_age/max_age and change_rate."""
    now = dt_util.utcnow()
    mock_data = {
        "return_time": datetime(now.year + 1, 8, 2, 12, 23, 42, tzinfo=dt_util.UTC)
    }

    def mock_now():
        return mock_data["return_time"]

    with patch(
        "homeassistant.components.statistics.sensor.dt_util.utcnow", new=mock_now
    ):
        assert await async_setup_component(
            hass,
            "sensor",
            {
                "sensor": {
                    "platform": "statistics",
                    "name": "test",
                    "entity_id": "sensor.test_monitored",
                }
            },
        )

        await hass.async_block_till_done()
        await hass.async_start()
        await hass.async_block_till_done()

        for value in stats.values:
            hass.states.async_set(
                "sensor.test_monitored",
                value,
                {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
            )
            await hass.async_block_till_done()
            # insert the next value one minute later
            mock_data["return_time"] += timedelta(minutes=1)

        state = hass.states.get("sensor.test")

    assert datetime(
        now.year + 1, 8, 2, 12, 23, 42, tzinfo=dt_util.UTC
    ) == state.attributes.get("min_age")
    assert datetime(
        now.year + 1, 8, 2, 12, 23 + stats.count - 1, 42, tzinfo=dt_util.UTC
    ) == state.attributes.get("max_age")
    assert stats.change_rate == state.attributes.get("change_rate")


async def test_initialize_from_database(hass, stats):
    """Test initializing the statistics from the database."""
    # enable the recorder
    await hass.async_add_executor_job(init_recorder_component, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    # store some values
    for value in stats.values:
        hass.states.async_set(
            "sensor.test_monitored", value, {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS}
        )
        await hass.async_block_till_done()
    # wait for the recorder to really store the data
    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()
    # only now create the statistics component, so that it must read the
    # data from the database
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "statistics",
                "name": "test",
                "entity_id": "sensor.test_monitored",
                "sampling_size": 100,
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # check if the result is as in test_sensor_source()
    state = hass.states.get("sensor.test")
    assert str(stats.mean) == state.state


async def test_initialize_from_database_with_maxage(hass, stats):
    """Test initializing the statistics from the database."""
    now = dt_util.utcnow()
    mock_data = {
        "return_time": datetime(now.year + 1, 8, 2, 12, 23, 42, tzinfo=dt_util.UTC)
    }

    def mock_now():
        return mock_data["return_time"]

    # Testing correct retrieval from recorder, thus we do not
    # want purging to occur within the class itself.
    def mock_purge(sensor):
        return

    # Set maximum age to 3 hours.
    max_age = 3
    # Determine what our minimum age should be based on test values.
    expected_min_age = mock_data["return_time"] + timedelta(
        hours=len(stats.values) - max_age
    )

    # enable the recorder
    await hass.async_add_executor_job(init_recorder_component, hass)
    await hass.async_block_till_done()
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    with patch(
        "homeassistant.components.statistics.sensor.dt_util.utcnow", new=mock_now
    ), patch.object(StatisticsSensor, "_purge_old", mock_purge):
        # store some values
        for value in stats.values:
            hass.states.async_set(
                "sensor.test_monitored",
                value,
                {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS},
            )
            await hass.async_block_till_done()
            # insert the next value 1 hour later
            mock_data["return_time"] += timedelta(hours=1)

        # wait for the recorder to really store the data
        await hass.async_add_executor_job(trigger_db_commit, hass)
        await hass.async_block_till_done()
        # only now create the statistics component, so that it must read
        # the data from the database
        assert await async_setup_component(
            hass,
            "sensor",
            {
                "sensor": {
                    "platform": "statistics",
                    "name": "test",
                    "entity_id": "sensor.test_monitored",
                    "sampling_size": 100,
                    "max_age": {"hours": max_age},
                }
            },
        )

        await hass.async_block_till_done()
        await hass.async_start()
        await hass.async_block_till_done()

        # check if the result is as in test_sensor_source()
        state = hass.states.get("sensor.test")

    assert expected_min_age == state.attributes.get("min_age")
    # The max_age timestamp should be 1 hour before what we have right
    # now in mock_data['return_time'].
    assert mock_data["return_time"] == state.attributes.get("max_age") + timedelta(
        hours=1
    )


async def test_reload(hass):
    """Verify we can reload filter sensors."""
    await hass.async_add_executor_job(
        init_recorder_component, hass
    )  # force in memory db

    hass.states.async_set("sensor.test_monitored", 12345)
    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "statistics",
                "name": "test",
                "entity_id": "sensor.test_monitored",
                "sampling_size": 100,
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("sensor.test")

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "statistics/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("sensor.test") is None
    assert hass.states.get("sensor.cputest")


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
