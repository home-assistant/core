"""The tests for sensor recorder platform."""
# pylint: disable=protected-access,invalid-name
from datetime import timedelta

import pytest

from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.components.recorder.models import StatisticsMeta
from homeassistant.components.recorder.util import session_scope
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, METRIC_SYSTEM

from tests.common import init_recorder_component

BATTERY_SENSOR_ATTRIBUTES = {
    "device_class": "battery",
    "state_class": "measurement",
    "unit_of_measurement": "%",
}
POWER_SENSOR_ATTRIBUTES = {
    "device_class": "power",
    "state_class": "measurement",
    "unit_of_measurement": "kW",
}
NONE_SENSOR_ATTRIBUTES = {
    "state_class": "measurement",
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


@pytest.mark.parametrize(
    "units, attributes, unit",
    [
        (IMPERIAL_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W"),
        (METRIC_SYSTEM, POWER_SENSOR_ATTRIBUTES, "W"),
        (IMPERIAL_SYSTEM, TEMPERATURE_SENSOR_ATTRIBUTES, "°F"),
        (METRIC_SYSTEM, TEMPERATURE_SENSOR_ATTRIBUTES, "°C"),
        (IMPERIAL_SYSTEM, PRESSURE_SENSOR_ATTRIBUTES, "psi"),
        (METRIC_SYSTEM, PRESSURE_SENSOR_ATTRIBUTES, "Pa"),
    ],
)
async def test_validate_statistics_supported_device_class(
    hass, hass_ws_client, units, attributes, unit
):
    """Test list_statistic_ids."""
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

    now = dt_util.utcnow()

    hass.config.units = units
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "sensor", {})
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    client = await hass_ws_client()

    # No statistics, no state - empty response
    await assert_validation_result(client, {})

    # No statistics, valid state - empty response
    hass.states.async_set(
        "sensor.test", 10, attributes={**attributes, **{"unit_of_measurement": unit}}
    )
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    await assert_validation_result(client, {})

    # No statistics, invalid state - empty response
    hass.states.async_set(
        "sensor.test", 11, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    await assert_validation_result(client, {})

    # Statistics has run, invalid state - expect error
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    hass.data[DATA_INSTANCE].do_adhoc_statistics(start=now)
    hass.states.async_set(
        "sensor.test", 12, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    expected = {
        "sensor.test": [
            {
                "data": {
                    "device_class": attributes["device_class"],
                    "state_unit": "dogs",
                    "statistic_id": "sensor.test",
                },
                "type": "unsupported_unit",
            }
        ],
    }
    await assert_validation_result(client, expected)

    # Valid state - empty response
    hass.states.async_set(
        "sensor.test", 13, attributes={**attributes, **{"unit_of_measurement": unit}}
    )
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    await assert_validation_result(client, {})

    # Valid state, statistic runs again - empty response
    hass.data[DATA_INSTANCE].do_adhoc_statistics(start=now)
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    await assert_validation_result(client, {})

    # Remove the state - empty response
    hass.states.async_remove("sensor.test")
    await assert_validation_result(client, {})


@pytest.mark.parametrize(
    "attributes",
    [BATTERY_SENSOR_ATTRIBUTES, NONE_SENSOR_ATTRIBUTES],
)
async def test_validate_statistics_unsupported_device_class(
    hass, hass_ws_client, attributes
):
    """Test list_statistic_ids."""
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

    async def assert_statistic_ids(expected_result):
        with session_scope(hass=hass) as session:
            db_states = list(session.query(StatisticsMeta))
            assert len(db_states) == len(expected_result)
            for i in range(len(db_states)):
                assert db_states[i].statistic_id == expected_result[i]["statistic_id"]
                assert (
                    db_states[i].unit_of_measurement
                    == expected_result[i]["unit_of_measurement"]
                )

    now = dt_util.utcnow()

    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "sensor", {})
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    client = await hass_ws_client()
    rec = hass.data[DATA_INSTANCE]

    # No statistics, no state - empty response
    await assert_validation_result(client, {})

    # No statistics, original unit - empty response
    hass.states.async_set("sensor.test", 10, attributes=attributes)
    await assert_validation_result(client, {})

    # No statistics, changed unit - empty response
    hass.states.async_set(
        "sensor.test", 11, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await assert_validation_result(client, {})

    # Run statistics, no statistics will be generated because of conflicting units
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    rec.do_adhoc_statistics(start=now)
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    await assert_statistic_ids([])

    # No statistics, changed unit - empty response
    hass.states.async_set(
        "sensor.test", 12, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await assert_validation_result(client, {})

    # Run statistics one hour later, only the "dogs" state will be considered
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    rec.do_adhoc_statistics(start=now + timedelta(hours=1))
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    await assert_statistic_ids(
        [{"statistic_id": "sensor.test", "unit_of_measurement": "dogs"}]
    )
    await assert_validation_result(client, {})

    # Change back to original unit - expect error
    hass.states.async_set("sensor.test", 13, attributes=attributes)
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    expected = {
        "sensor.test": [
            {
                "data": {
                    "metadata_unit": "dogs",
                    "state_unit": attributes.get("unit_of_measurement"),
                    "statistic_id": "sensor.test",
                },
                "type": "units_changed",
            }
        ],
    }
    await assert_validation_result(client, expected)

    # Changed unit - empty response
    hass.states.async_set(
        "sensor.test", 14, attributes={**attributes, **{"unit_of_measurement": "dogs"}}
    )
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    await assert_validation_result(client, {})

    # Valid state, statistic runs again - empty response
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    hass.data[DATA_INSTANCE].do_adhoc_statistics(start=now)
    await hass.async_add_executor_job(hass.data[DATA_INSTANCE].block_till_done)
    await assert_validation_result(client, {})

    # Remove the state - empty response
    hass.states.async_remove("sensor.test")
    await assert_validation_result(client, {})
