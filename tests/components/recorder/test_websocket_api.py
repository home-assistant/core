"""The tests for sensor recorder platform."""
# pylint: disable=protected-access,invalid-name
from datetime import timedelta
import threading
from unittest.mock import patch

import pytest
from pytest import approx

from homeassistant.components import recorder
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM

from .common import (
    async_wait_recording_done_without_instance,
    create_engine_test,
    trigger_db_commit,
)

from tests.common import (
    async_fire_time_changed,
    async_init_recorder_component,
    init_recorder_component,
)

POWER_SENSOR_ATTRIBUTES = {
    "device_class": "power",
    "state_class": "measurement",
    "unit_of_measurement": "kW",
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


async def test_validate_statistics(hass, hass_ws_client):
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
    await hass.async_add_executor_job(init_recorder_component, hass)
    client = await hass_ws_client()
    await assert_validation_result(client, {})


async def test_clear_statistics(hass, hass_ws_client):
    """Test removing statistics."""
    now = dt_util.utcnow()

    units = METRIC_SYSTEM
    attributes = POWER_SENSOR_ATTRIBUTES
    state = 10
    value = 10000

    hass.config.units = units
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    hass.states.async_set("sensor.test1", state, attributes=attributes)
    hass.states.async_set("sensor.test2", state * 2, attributes=attributes)
    hass.states.async_set("sensor.test3", state * 3, attributes=attributes)
    await hass.async_block_till_done()

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()

    hass.data[DATA_INSTANCE].do_adhoc_statistics(start=now)
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "history/statistics_during_period",
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
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 3,
            "type": "history/statistics_during_period",
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
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 5,
            "type": "history/statistics_during_period",
            "start_time": now.isoformat(),
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"sensor.test2": expected_response["sensor.test2"]}


@pytest.mark.parametrize("new_unit", ["dogs", None])
async def test_update_statistics_metadata(hass, hass_ws_client, new_unit):
    """Test removing statistics."""
    now = dt_util.utcnow()

    units = METRIC_SYSTEM
    attributes = POWER_SENSOR_ATTRIBUTES
    state = 10

    hass.config.units = units
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "history", {})
    await async_setup_component(hass, "sensor", {})
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    hass.states.async_set("sensor.test", state, attributes=attributes)
    await hass.async_block_till_done()

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()

    hass.data[DATA_INSTANCE].do_adhoc_statistics(period="hourly", start=now)
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)

    client = await hass_ws_client()

    await client.send_json({"id": 1, "type": "history/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "name": None,
            "source": "recorder",
            "unit_of_measurement": "W",
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
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)

    await client.send_json({"id": 3, "type": "history/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "name": None,
            "source": "recorder",
            "unit_of_measurement": new_unit,
        }
    ]


async def test_recorder_info(hass, hass_ws_client):
    """Test getting recorder status."""
    client = await hass_ws_client()
    await async_init_recorder_component(hass)

    # Ensure there are no queued events
    await async_wait_recording_done_without_instance(hass)

    await client.send_json({"id": 1, "type": "recorder/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "backlog": 0,
        "max_backlog": 30000,
        "migration_in_progress": False,
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
        assert not await async_setup_component(
            hass, recorder.DOMAIN, {recorder.DOMAIN: config}
        )
        assert recorder.DOMAIN not in hass.config.components
    await hass.async_block_till_done()

    # Wait for recorder to shut down
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].join)

    await client.send_json({"id": 1, "type": "recorder/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["recording"] is False
    assert response["result"]["thread_running"] is False


async def test_recorder_info_migration_queue_exhausted(hass, hass_ws_client):
    """Test getting recorder status when recorder queue is exhausted."""
    assert recorder.util.async_migration_in_progress(hass) is False

    migration_done = threading.Event()

    real_migration = recorder.migration.migrate_schema

    def stalled_migration(*args):
        """Make migration stall."""
        nonlocal migration_done
        migration_done.wait()
        return real_migration(*args)

    with patch(
        "homeassistant.components.recorder.Recorder.async_periodic_statistics"
    ), patch(
        "homeassistant.components.recorder.create_engine", new=create_engine_test
    ), patch.object(
        recorder, "MAX_QUEUE_BACKLOG", 1
    ), patch(
        "homeassistant.components.recorder.migration.migrate_schema",
        wraps=stalled_migration,
    ):
        await async_setup_component(
            hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
        )
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
    await async_wait_recording_done_without_instance(hass)

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


async def test_backup_start_timeout(hass, hass_ws_client, hass_supervisor_access_token):
    """Test getting backup start when recorder is not present."""
    client = await hass_ws_client(hass, hass_supervisor_access_token)
    await async_init_recorder_component(hass)

    # Ensure there are no queued events
    await async_wait_recording_done_without_instance(hass)

    with patch.object(recorder, "DB_LOCK_TIMEOUT", 0):
        try:
            await client.send_json({"id": 1, "type": "backup/start"})
            response = await client.receive_json()
            assert not response["success"]
            assert response["error"]["code"] == "timeout_error"
        finally:
            await client.send_json({"id": 2, "type": "backup/end"})


async def test_backup_end(hass, hass_ws_client, hass_supervisor_access_token):
    """Test backup start."""
    client = await hass_ws_client(hass, hass_supervisor_access_token)
    await async_init_recorder_component(hass)

    # Ensure there are no queued events
    await async_wait_recording_done_without_instance(hass)

    await client.send_json({"id": 1, "type": "backup/start"})
    response = await client.receive_json()
    assert response["success"]

    await client.send_json({"id": 2, "type": "backup/end"})
    response = await client.receive_json()
    assert response["success"]


async def test_backup_end_without_start(
    hass, hass_ws_client, hass_supervisor_access_token
):
    """Test backup start."""
    client = await hass_ws_client(hass, hass_supervisor_access_token)
    await async_init_recorder_component(hass)

    # Ensure there are no queued events
    await async_wait_recording_done_without_instance(hass)

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
async def test_get_statistics_metadata(hass, hass_ws_client, units, attributes, unit):
    """Test get_statistics_metadata."""
    now = dt_util.utcnow()

    hass.config.units = units
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "history", {"history": {}})
    await async_setup_component(hass, "sensor", {})
    await async_init_recorder_component(hass)
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

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
    await hass.async_block_till_done()

    await hass.async_add_executor_job(trigger_db_commit, hass)
    await hass.async_block_till_done()

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
            "name": None,
            "source": "recorder",
            "unit_of_measurement": unit,
        }
    ]

    hass.data[recorder.DATA_INSTANCE].do_adhoc_statistics(start=now)
    await hass.async_add_executor_job(hass.data[recorder.DATA_INSTANCE].block_till_done)
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
            "name": None,
            "source": "recorder",
            "unit_of_measurement": unit,
        }
    ]

    await client.send_json(
        {
            "id": 4,
            "type": "recorder/get_statistics_metadata",
            "statistic_type": "sum",
            "statistic_ids": ["test:total_gas"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "test:total_gas",
            "name": "Total imported energy",
            "source": "test",
            "unit_of_measurement": unit,
        }
    ]
