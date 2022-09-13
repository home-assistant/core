"""The tests for sensor recorder platform."""
# pylint: disable=protected-access,invalid-name
from datetime import timedelta
import threading
from unittest.mock import patch

from freezegun import freeze_time
import pytest
from pytest import approx

from homeassistant.components import recorder
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    get_metadata,
    list_statistic_ids,
    statistics_during_period,
)
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from .common import (
    async_recorder_block_till_done,
    async_wait_recording_done,
    create_engine_test,
    do_adhoc_statistics,
)

from tests.common import async_fire_time_changed

POWER_SENSOR_ATTRIBUTES = {
    "device_class": "power",
    "state_class": "measurement",
    "unit_of_measurement": "kW",
}
PRESSURE_SENSOR_ATTRIBUTES = {
    "device_class": "pressure",
    "state_class": "measurement",
    "unit_of_measurement": "hPa",
}
TEMPERATURE_SENSOR_ATTRIBUTES = {
    "device_class": "temperature",
    "state_class": "measurement",
    "unit_of_measurement": "°C",
}
ENERGY_SENSOR_ATTRIBUTES = {
    "device_class": "energy",
    "state_class": "total",
    "unit_of_measurement": "kWh",
}
GAS_SENSOR_ATTRIBUTES = {
    "device_class": "gas",
    "state_class": "total",
    "unit_of_measurement": "m³",
}


@pytest.mark.parametrize(
    "units, attributes, state, value",
    [
        (IMPERIAL_SYSTEM, POWER_SENSOR_ATTRIBUTES, 10, 10000),
        (METRIC_SYSTEM, POWER_SENSOR_ATTRIBUTES, 10, 10000),
        (IMPERIAL_SYSTEM, TEMPERATURE_SENSOR_ATTRIBUTES, 10, 50),
        (METRIC_SYSTEM, TEMPERATURE_SENSOR_ATTRIBUTES, 10, 10),
        (IMPERIAL_SYSTEM, PRESSURE_SENSOR_ATTRIBUTES, 1000, 14.503774389728312),
        (METRIC_SYSTEM, PRESSURE_SENSOR_ATTRIBUTES, 1000, 100000),
    ],
)
async def test_statistics_during_period(
    hass, hass_ws_client, recorder_mock, units, attributes, state, value
):
    """Test statistics_during_period."""
    now = dt_util.utcnow()

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", state, attributes=attributes)
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, start=now)
    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "end_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "hour",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {}

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "sensor.test": [
            {
                "statistic_id": "sensor.test",
                "start": now.isoformat(),
                "end": (now + timedelta(minutes=5)).isoformat(),
                "mean": approx(value),
                "min": approx(value),
                "max": approx(value),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }


@pytest.mark.parametrize(
    "units, attributes, state, value",
    [
        (IMPERIAL_SYSTEM, POWER_SENSOR_ATTRIBUTES, 10, 10000),
        (METRIC_SYSTEM, POWER_SENSOR_ATTRIBUTES, 10, 10000),
        (IMPERIAL_SYSTEM, TEMPERATURE_SENSOR_ATTRIBUTES, 10, 50),
        (METRIC_SYSTEM, TEMPERATURE_SENSOR_ATTRIBUTES, 10, 10),
        (IMPERIAL_SYSTEM, PRESSURE_SENSOR_ATTRIBUTES, 1000, 14.503774389728312),
        (METRIC_SYSTEM, PRESSURE_SENSOR_ATTRIBUTES, 1000, 100000),
    ],
)
async def test_statistics_during_period_in_the_past(
    hass, hass_ws_client, recorder_mock, units, attributes, state, value
):
    """Test statistics_during_period in the past."""
    hass.config.set_time_zone("UTC")
    now = dt_util.utcnow().replace()

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    past = now - timedelta(days=3)

    with freeze_time(past):
        hass.states.async_set("sensor.test", state, attributes=attributes)
        await async_wait_recording_done(hass)

    sensor_state = hass.states.get("sensor.test")
    assert sensor_state.last_updated == past

    stats_top_of_hour = past.replace(minute=0, second=0, microsecond=0)
    stats_start = past.replace(minute=55)
    do_adhoc_statistics(hass, start=stats_start)
    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "end_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "hour",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {}

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {}

    past = now - timedelta(days=3, hours=1)
    await client.send_json(
        {
            "id": 3,
            "type": "recorder/statistics_during_period",
            "start_time": past.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "sensor.test": [
            {
                "statistic_id": "sensor.test",
                "start": stats_start.isoformat(),
                "end": (stats_start + timedelta(minutes=5)).isoformat(),
                "mean": approx(value),
                "min": approx(value),
                "max": approx(value),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }

    start_of_day = stats_top_of_hour.replace(hour=0, minute=0)
    await client.send_json(
        {
            "id": 4,
            "type": "recorder/statistics_during_period",
            "start_time": stats_top_of_hour.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "day",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "sensor.test": [
            {
                "statistic_id": "sensor.test",
                "start": start_of_day.isoformat(),
                "end": (start_of_day + timedelta(days=1)).isoformat(),
                "mean": approx(value),
                "min": approx(value),
                "max": approx(value),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ]
    }

    await client.send_json(
        {
            "id": 5,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {}


async def test_statistics_during_period_bad_start_time(
    hass, hass_ws_client, recorder_mock
):
    """Test statistics_during_period."""
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": "cats",
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_start_time"


async def test_statistics_during_period_bad_end_time(
    hass, hass_ws_client, recorder_mock
):
    """Test statistics_during_period."""
    now = dt_util.utcnow()

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "end_time": "dogs",
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_end_time"


@pytest.mark.parametrize(
    "units, attributes, display_unit, statistics_unit",
    [
        (IMPERIAL_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W", "W"),
        (METRIC_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W", "W"),
        (IMPERIAL_SYSTEM, TEMPERATURE_SENSOR_ATTRIBUTES, "°F", "°C"),
        (METRIC_SYSTEM, TEMPERATURE_SENSOR_ATTRIBUTES, "°C", "°C"),
        (IMPERIAL_SYSTEM, PRESSURE_SENSOR_ATTRIBUTES, "psi", "Pa"),
        (METRIC_SYSTEM, PRESSURE_SENSOR_ATTRIBUTES, "Pa", "Pa"),
    ],
)
async def test_list_statistic_ids(
    hass,
    hass_ws_client,
    recorder_mock,
    units,
    attributes,
    display_unit,
    statistics_unit,
):
    """Test list_statistic_ids."""
    now = dt_util.utcnow()

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json({"id": 1, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    hass.states.async_set("sensor.test", 10, attributes=attributes)
    await async_wait_recording_done(hass)

    await client.send_json({"id": 2, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "display_unit_of_measurement": display_unit,
            "statistics_unit_of_measurement": statistics_unit,
        }
    ]

    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    # Remove the state, statistics will now be fetched from the database
    hass.states.async_remove("sensor.test")
    await hass.async_block_till_done()

    await client.send_json({"id": 3, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "display_unit_of_measurement": display_unit,
            "statistics_unit_of_measurement": statistics_unit,
        }
    ]

    await client.send_json(
        {"id": 4, "type": "recorder/list_statistic_ids", "statistic_type": "dogs"}
    )
    response = await client.receive_json()
    assert not response["success"]

    await client.send_json(
        {"id": 5, "type": "recorder/list_statistic_ids", "statistic_type": "mean"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "display_unit_of_measurement": display_unit,
            "statistics_unit_of_measurement": statistics_unit,
        }
    ]

    await client.send_json(
        {"id": 6, "type": "recorder/list_statistic_ids", "statistic_type": "sum"}
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []


async def test_validate_statistics(hass, hass_ws_client, recorder_mock):
    """Test validate_statistics can be called."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_validation_result(client, expected_result):
        await client.send_json(
            {"id": next_id(), "type": "recorder/validate_statistics"}
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expected_result

    # No statistics, no state - empty response
    client = await hass_ws_client()
    await assert_validation_result(client, {})


async def test_clear_statistics(hass, hass_ws_client, recorder_mock):
    """Test removing statistics."""
    now = dt_util.utcnow()

    units = METRIC_SYSTEM
    attributes = POWER_SENSOR_ATTRIBUTES
    state = 10
    value = 10000

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test1", state, attributes=attributes)
    hass.states.async_set("sensor.test2", state * 2, attributes=attributes)
    hass.states.async_set("sensor.test3", state * 3, attributes=attributes)
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    expected_response = {
        "sensor.test1": [
            {
                "statistic_id": "sensor.test1",
                "start": now.isoformat(),
                "end": (now + timedelta(minutes=5)).isoformat(),
                "mean": approx(value),
                "min": approx(value),
                "max": approx(value),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
        "sensor.test2": [
            {
                "statistic_id": "sensor.test2",
                "start": now.isoformat(),
                "end": (now + timedelta(minutes=5)).isoformat(),
                "mean": approx(value * 2),
                "min": approx(value * 2),
                "max": approx(value * 2),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
        "sensor.test3": [
            {
                "statistic_id": "sensor.test3",
                "start": now.isoformat(),
                "end": (now + timedelta(minutes=5)).isoformat(),
                "mean": approx(value * 3),
                "min": approx(value * 3),
                "max": approx(value * 3),
                "last_reset": None,
                "state": None,
                "sum": None,
            }
        ],
    }
    assert response["result"] == expected_response

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/clear_statistics",
            "statistic_ids": ["sensor.test"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 3,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == expected_response

    await client.send_json(
        {
            "id": 4,
            "type": "recorder/clear_statistics",
            "statistic_ids": ["sensor.test1", "sensor.test3"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 5,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"sensor.test2": expected_response["sensor.test2"]}


@pytest.mark.parametrize("new_unit", ["dogs", None])
async def test_update_statistics_metadata(
    hass, hass_ws_client, recorder_mock, new_unit
):
    """Test removing statistics."""
    now = dt_util.utcnow()

    units = METRIC_SYSTEM
    attributes = POWER_SENSOR_ATTRIBUTES
    state = 10

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", state, attributes=attributes)
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, period="hourly", start=now)
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()

    await client.send_json({"id": 1, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": "W",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "W",
        }
    ]

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/update_statistics_metadata",
            "statistic_id": "sensor.test",
            "unit_of_measurement": new_unit,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_recorder_block_till_done(hass)

    await client.send_json({"id": 3, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": new_unit,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": new_unit,
        }
    ]


async def test_recorder_info(hass, hass_ws_client, recorder_mock):
    """Test getting recorder status."""
    client = await hass_ws_client()

    # Ensure there are no queued events
    await async_wait_recording_done(hass)

    await client.send_json({"id": 1, "type": "recorder/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "backlog": 0,
        "max_backlog": 40000,
        "migration_in_progress": False,
        "migration_is_live": False,
        "recording": True,
        "thread_running": True,
    }


async def test_recorder_info_no_recorder(hass, hass_ws_client):
    """Test getting recorder status when recorder is not present."""
    client = await hass_ws_client()

    await client.send_json({"id": 1, "type": "recorder/info"})
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "unknown_command"


async def test_recorder_info_bad_recorder_config(hass, hass_ws_client):
    """Test getting recorder status when recorder is not started."""
    config = {recorder.CONF_DB_URL: "sqlite://no_file", recorder.CONF_DB_RETRY_WAIT: 0}

    client = await hass_ws_client()

    with patch("homeassistant.components.recorder.migration.migrate_schema"):
        recorder_helper.async_initialize_recorder(hass)
        assert not await async_setup_component(
            hass, recorder.DOMAIN, {recorder.DOMAIN: config}
        )
        assert recorder.DOMAIN not in hass.config.components
    await hass.async_block_till_done()

    # Wait for recorder to shut down
    await hass.async_add_executor_job(recorder.get_instance(hass).join)

    await client.send_json({"id": 1, "type": "recorder/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["recording"] is False
    assert response["result"]["thread_running"] is False


async def test_recorder_info_migration_queue_exhausted(hass, hass_ws_client):
    """Test getting recorder status when recorder queue is exhausted."""
    assert recorder.util.async_migration_in_progress(hass) is False

    migration_done = threading.Event()

    real_migration = recorder.migration._apply_update

    def stalled_migration(*args):
        """Make migration stall."""
        nonlocal migration_done
        migration_done.wait()
        return real_migration(*args)

    with patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True), patch(
        "homeassistant.components.recorder.Recorder.async_periodic_statistics"
    ), patch(
        "homeassistant.components.recorder.core.create_engine",
        new=create_engine_test,
    ), patch.object(
        recorder.core, "MAX_QUEUE_BACKLOG", 1
    ), patch(
        "homeassistant.components.recorder.migration._apply_update",
        wraps=stalled_migration,
    ):
        recorder_helper.async_initialize_recorder(hass)
        hass.create_task(
            async_setup_component(
                hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
            )
        )
        await recorder_helper.async_wait_recorder(hass)
        hass.states.async_set("my.entity", "on", {})
        await hass.async_block_till_done()

        # Detect queue full
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=2))
        await hass.async_block_till_done()

        client = await hass_ws_client()

        # Check the status
        await client.send_json({"id": 1, "type": "recorder/info"})
        response = await client.receive_json()
        assert response["success"]
        assert response["result"]["migration_in_progress"] is True
        assert response["result"]["recording"] is False
        assert response["result"]["thread_running"] is True

    # Let migration finish
    migration_done.set()
    await async_wait_recording_done(hass)

    # Check the status after migration finished
    await client.send_json({"id": 2, "type": "recorder/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["migration_in_progress"] is False
    assert response["result"]["recording"] is True
    assert response["result"]["thread_running"] is True


async def test_backup_start_no_recorder(
    hass, hass_ws_client, hass_supervisor_access_token
):
    """Test getting backup start when recorder is not present."""
    client = await hass_ws_client(hass, hass_supervisor_access_token)

    await client.send_json({"id": 1, "type": "backup/start"})
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "unknown_command"


async def test_backup_start_timeout(
    hass, hass_ws_client, hass_supervisor_access_token, recorder_mock
):
    """Test getting backup start when recorder is not present."""
    client = await hass_ws_client(hass, hass_supervisor_access_token)

    # Ensure there are no queued events
    await async_wait_recording_done(hass)

    with patch.object(recorder.core, "DB_LOCK_TIMEOUT", 0):
        try:
            await client.send_json({"id": 1, "type": "backup/start"})
            response = await client.receive_json()
            assert not response["success"]
            assert response["error"]["code"] == "timeout_error"
        finally:
            await client.send_json({"id": 2, "type": "backup/end"})


async def test_backup_end(
    hass, hass_ws_client, hass_supervisor_access_token, recorder_mock
):
    """Test backup start."""
    client = await hass_ws_client(hass, hass_supervisor_access_token)

    # Ensure there are no queued events
    await async_wait_recording_done(hass)

    await client.send_json({"id": 1, "type": "backup/start"})
    response = await client.receive_json()
    assert response["success"]

    await client.send_json({"id": 2, "type": "backup/end"})
    response = await client.receive_json()
    assert response["success"]


async def test_backup_end_without_start(
    hass, hass_ws_client, hass_supervisor_access_token, recorder_mock
):
    """Test backup start."""
    client = await hass_ws_client(hass, hass_supervisor_access_token)

    # Ensure there are no queued events
    await async_wait_recording_done(hass)

    await client.send_json({"id": 1, "type": "backup/end"})
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "database_unlock_failed"


@pytest.mark.parametrize(
    "units, attributes, unit",
    [
        (METRIC_SYSTEM, GAS_SENSOR_ATTRIBUTES, "m³"),
        (METRIC_SYSTEM, ENERGY_SENSOR_ATTRIBUTES, "kWh"),
    ],
)
async def test_get_statistics_metadata(
    hass, hass_ws_client, recorder_mock, units, attributes, unit
):
    """Test get_statistics_metadata."""
    now = dt_util.utcnow()

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json({"id": 1, "type": "recorder/get_statistics_metadata"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    period1 = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 23:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 23:00:00"))
    external_energy_statistics_1 = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 2,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 5,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 8,
        },
    )
    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_gas",
        "unit_of_measurement": unit,
    }

    async_add_external_statistics(
        hass, external_energy_metadata_1, external_energy_statistics_1
    )

    hass.states.async_set("sensor.test", 10, attributes=attributes)
    await async_wait_recording_done(hass)

    hass.states.async_set("sensor.test2", 10, attributes=attributes)
    await async_wait_recording_done(hass)

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/get_statistics_metadata",
            "statistic_ids": ["sensor.test"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": unit,
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": unit,
        }
    ]

    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    # Remove the state, statistics will now be fetched from the database
    hass.states.async_remove("sensor.test")
    await hass.async_block_till_done()

    await client.send_json(
        {
            "id": 3,
            "type": "recorder/get_statistics_metadata",
            "statistic_ids": ["sensor.test"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": unit,
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": unit,
        }
    ]


@pytest.mark.parametrize(
    "source, statistic_id",
    (
        ("test", "test:total_energy_import"),
        ("recorder", "sensor.total_energy_import"),
    ),
)
async def test_import_statistics(
    hass, hass_ws_client, recorder_mock, caplog, source, statistic_id
):
    """Test importing statistics."""
    client = await hass_ws_client()

    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    period2 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)

    external_statistics1 = {
        "start": period1.isoformat(),
        "last_reset": None,
        "state": 0,
        "sum": 2,
    }
    external_statistics2 = {
        "start": period2.isoformat(),
        "last_reset": None,
        "state": 1,
        "sum": 3,
    }

    external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": source,
        "statistic_id": statistic_id,
        "unit_of_measurement": "kWh",
    }

    await client.send_json(
        {
            "id": 1,
            "type": "recorder/import_statistics",
            "metadata": external_metadata,
            "stats": [external_statistics1, external_statistics2],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None

    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "statistic_id": statistic_id,
                "start": period1.isoformat(),
                "end": (period1 + timedelta(hours=1)).isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(0.0),
                "sum": approx(2.0),
            },
            {
                "statistic_id": statistic_id,
                "start": period2.isoformat(),
                "end": (period2 + timedelta(hours=1)).isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(1.0),
                "sum": approx(3.0),
            },
        ]
    }
    statistic_ids = list_statistic_ids(hass)  # TODO
    assert statistic_ids == [
        {
            "display_unit_of_measurement": "kWh",
            "has_mean": False,
            "has_sum": True,
            "statistic_id": statistic_id,
            "name": "Total imported energy",
            "source": source,
            "statistics_unit_of_measurement": "kWh",
        }
    ]
    metadata = get_metadata(hass, statistic_ids=(statistic_id,))
    assert metadata == {
        statistic_id: (
            1,
            {
                "has_mean": False,
                "has_sum": True,
                "name": "Total imported energy",
                "source": source,
                "statistic_id": statistic_id,
                "unit_of_measurement": "kWh",
            },
        )
    }
    last_stats = get_last_statistics(hass, 1, statistic_id, True)
    assert last_stats == {
        statistic_id: [
            {
                "statistic_id": statistic_id,
                "start": period2.isoformat(),
                "end": (period2 + timedelta(hours=1)).isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(1.0),
                "sum": approx(3.0),
            },
        ]
    }

    # Update the previously inserted statistics
    external_statistics = {
        "start": period1.isoformat(),
        "last_reset": None,
        "state": 5,
        "sum": 6,
    }

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/import_statistics",
            "metadata": external_metadata,
            "stats": [external_statistics],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None

    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "statistic_id": statistic_id,
                "start": period1.isoformat(),
                "end": (period1 + timedelta(hours=1)).isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(5.0),
                "sum": approx(6.0),
            },
            {
                "statistic_id": statistic_id,
                "start": period2.isoformat(),
                "end": (period2 + timedelta(hours=1)).isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(1.0),
                "sum": approx(3.0),
            },
        ]
    }

    # Update the previously inserted statistics
    external_statistics = {
        "start": period1.isoformat(),
        "max": 1,
        "mean": 2,
        "min": 3,
        "last_reset": None,
        "state": 4,
        "sum": 5,
    }

    await client.send_json(
        {
            "id": 3,
            "type": "recorder/import_statistics",
            "metadata": external_metadata,
            "stats": [external_statistics],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None

    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "statistic_id": statistic_id,
                "start": period1.isoformat(),
                "end": (period1 + timedelta(hours=1)).isoformat(),
                "max": approx(1.0),
                "mean": approx(2.0),
                "min": approx(3.0),
                "last_reset": None,
                "state": approx(4.0),
                "sum": approx(5.0),
            },
            {
                "statistic_id": statistic_id,
                "start": period2.isoformat(),
                "end": (period2 + timedelta(hours=1)).isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(1.0),
                "sum": approx(3.0),
            },
        ]
    }

    await client.send_json(
        {
            "id": 4,
            "type": "recorder/adjust_sum_statistics",
            "statistic_id": statistic_id,
            "start_time": period2.isoformat(),
            "adjustment": 1000.0,
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "statistic_id": statistic_id,
                "start": period1.isoformat(),
                "end": (period1 + timedelta(hours=1)).isoformat(),
                "max": approx(1.0),
                "mean": approx(2.0),
                "min": approx(3.0),
                "last_reset": None,
                "state": approx(4.0),
                "sum": approx(5.0),
            },
            {
                "statistic_id": statistic_id,
                "start": period2.isoformat(),
                "end": (period2 + timedelta(hours=1)).isoformat(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": approx(1.0),
                "sum": approx(1003.0),
            },
        ]
    }
