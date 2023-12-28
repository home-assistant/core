"""The test for the statistics sensor platform."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
import statistics
from typing import Any
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant import config as hass_config
from homeassistant.components.recorder import Recorder
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.statistics import DOMAIN as STATISTICS_DOMAIN
from homeassistant.components.statistics.sensor import StatisticsSensor
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    DEGREE,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed, get_fixture_path
from tests.components.recorder.common import async_wait_recording_done

VALUES_BINARY = ["on", "off", "on", "off", "on", "off", "on", "off", "on"]
VALUES_NUMERIC = [17, 20, 15.2, 5, 3.8, 9.2, 6.7, 14, 6]


async def test_unique_id(hass: HomeAssistant) -> None:
    """Test configuration defined unique_id."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test",
                    "unique_id": "uniqueid_sensor_test",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    entity_reg = er.async_get(hass)
    entity_id = entity_reg.async_get_entity_id(
        "sensor", STATISTICS_DOMAIN, "uniqueid_sensor_test"
    )
    assert entity_id == "sensor.test"


async def test_sensor_defaults_numeric(hass: HomeAssistant) -> None:
    """Test the general behavior of the sensor, with numeric source sensor."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    for value in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert state is not None
    assert state.state == str(round(sum(VALUES_NUMERIC) / len(VALUES_NUMERIC), 2))
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get("buffer_usage_ratio") == round(9 / 20, 2)
    assert state.attributes.get("source_value_valid") is True
    assert "age_coverage_ratio" not in state.attributes

    # Source sensor turns unavailable, then available with valid value,
    # statistics sensor should follow
    state = hass.states.get("sensor.test")
    hass.states.async_set(
        "sensor.test_monitored",
        STATE_UNAVAILABLE,
    )
    await hass.async_block_till_done()
    new_state = hass.states.get("sensor.test")
    assert new_state is not None
    assert new_state.state == STATE_UNAVAILABLE
    assert new_state.attributes.get("source_value_valid") is None
    hass.states.async_set(
        "sensor.test_monitored",
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()
    new_state = hass.states.get("sensor.test")
    new_mean = round(sum(VALUES_NUMERIC) / (len(VALUES_NUMERIC) + 1), 2)
    assert new_state is not None
    assert new_state.state == str(new_mean)
    assert (
        new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    )
    assert new_state.attributes.get("buffer_usage_ratio") == round(10 / 20, 2)
    assert new_state.attributes.get("source_value_valid") is True

    # Source sensor has a nonnumerical state, unit and state should not change
    state = hass.states.get("sensor.test")
    hass.states.async_set("sensor.test_monitored", "beer", {})
    await hass.async_block_till_done()
    new_state = hass.states.get("sensor.test")
    assert new_state is not None
    assert new_state.state == str(new_mean)
    assert (
        new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    )
    assert new_state.attributes.get("source_value_valid") is False

    # Source sensor has the STATE_UNKNOWN state, unit and state should not change
    state = hass.states.get("sensor.test")
    hass.states.async_set("sensor.test_monitored", STATE_UNKNOWN, {})
    await hass.async_block_till_done()
    new_state = hass.states.get("sensor.test")
    assert new_state is not None
    assert new_state.state == str(new_mean)
    assert (
        new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    )
    assert new_state.attributes.get("source_value_valid") is False

    # Source sensor is removed, unit and state should not change
    # This is equal to a None value being published
    hass.states.async_remove("sensor.test_monitored")
    await hass.async_block_till_done()
    new_state = hass.states.get("sensor.test")
    assert new_state is not None
    assert new_state.state == str(new_mean)
    assert (
        new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    )
    assert new_state.attributes.get("source_value_valid") is False


async def test_sensor_defaults_binary(hass: HomeAssistant) -> None:
    """Test the general behavior of the sensor, with binary source sensor."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test",
                    "entity_id": "binary_sensor.test_monitored",
                    "state_characteristic": "count",
                    "sampling_size": 20,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    for value in VALUES_BINARY:
        hass.states.async_set(
            "binary_sensor.test_monitored",
            value,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert state is not None
    assert state.state == str(len(VALUES_BINARY))
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get("buffer_usage_ratio") == round(9 / 20, 2)
    assert state.attributes.get("source_value_valid") is True
    assert "age_coverage_ratio" not in state.attributes


async def test_sensor_source_with_force_update(hass: HomeAssistant) -> None:
    """Test the behavior of the sensor when the source sensor force-updates with same value."""
    repeating_values = [18, 0, 0, 0, 0, 0, 0, 0, 9]
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test_normal",
                    "entity_id": "sensor.test_monitored_normal",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                },
                {
                    "platform": "statistics",
                    "name": "test_force",
                    "entity_id": "sensor.test_monitored_force",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    for value in repeating_values:
        hass.states.async_set(
            "sensor.test_monitored_normal",
            str(value),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        )
        hass.states.async_set(
            "sensor.test_monitored_force",
            str(value),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
            force_update=True,
        )
    await hass.async_block_till_done()

    state_normal = hass.states.get("sensor.test_normal")
    state_force = hass.states.get("sensor.test_force")
    assert state_normal and state_force
    assert state_normal.state == str(round(sum(repeating_values) / 3, 2))
    assert state_force.state == str(round(sum(repeating_values) / 9, 2))
    assert state_normal.attributes.get("buffer_usage_ratio") == round(3 / 20, 2)
    assert state_force.attributes.get("buffer_usage_ratio") == round(9 / 20, 2)


async def test_sampling_boundaries_given(hass: HomeAssistant) -> None:
    """Test if either sampling_size or max_age are given."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test_boundaries_none",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                },
                {
                    "platform": "statistics",
                    "name": "test_boundaries_size",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                },
                {
                    "platform": "statistics",
                    "name": "test_boundaries_age",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "max_age": {"minutes": 4},
                },
                {
                    "platform": "statistics",
                    "name": "test_boundaries_both",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                    "max_age": {"minutes": 4},
                },
            ]
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "sensor.test_monitored",
        str(VALUES_NUMERIC[0]),
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_boundaries_none")
    assert state is None
    state = hass.states.get("sensor.test_boundaries_size")
    assert state is not None
    state = hass.states.get("sensor.test_boundaries_age")
    assert state is not None
    state = hass.states.get("sensor.test_boundaries_both")
    assert state is not None


async def test_sampling_size_reduced(hass: HomeAssistant) -> None:
    """Test limited buffer size."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "sampling_size": 5,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    for value in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    new_mean = round(sum(VALUES_NUMERIC[-5:]) / len(VALUES_NUMERIC[-5:]), 2)
    assert state is not None
    assert state.state == str(new_mean)
    assert state.attributes.get("buffer_usage_ratio") == round(5 / 5, 2)


async def test_sampling_size_1(hass: HomeAssistant) -> None:
    """Test validity of stats requiring only one sample."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "sampling_size": 1,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    for value in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    new_mean = float(VALUES_NUMERIC[-1])
    assert state is not None
    assert state.state == str(new_mean)
    assert state.attributes.get("buffer_usage_ratio") == round(1 / 1, 2)


async def test_age_limit_expiry(hass: HomeAssistant) -> None:
    """Test that values are removed with given max age."""
    now = dt_util.utcnow()
    current_time = datetime(now.year + 1, 8, 2, 12, 23, tzinfo=dt_util.UTC)

    with freeze_time(current_time) as freezer:
        assert await async_setup_component(
            hass,
            "sensor",
            {
                "sensor": [
                    {
                        "platform": "statistics",
                        "name": "test",
                        "entity_id": "sensor.test_monitored",
                        "state_characteristic": "mean",
                        "sampling_size": 20,
                        "max_age": {"minutes": 4},
                    },
                ]
            },
        )
        await hass.async_block_till_done()

        for value in VALUES_NUMERIC:
            current_time += timedelta(minutes=1)
            freezer.move_to(current_time)
            async_fire_time_changed(hass, current_time)
            hass.states.async_set(
                "sensor.test_monitored",
                str(value),
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
            )
        await hass.async_block_till_done()

        # After adding all values, we should only see 5 values in memory

        state = hass.states.get("sensor.test")
        new_mean = round(sum(VALUES_NUMERIC[-5:]) / len(VALUES_NUMERIC[-5:]), 2)
        assert state is not None
        assert state.state == str(new_mean)
        assert state.attributes.get("buffer_usage_ratio") == round(5 / 20, 2)
        assert state.attributes.get("age_coverage_ratio") == 1.0

        # Values expire over time. Only two are left

        current_time += timedelta(minutes=3)
        freezer.move_to(current_time)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test")
        new_mean = round(sum(VALUES_NUMERIC[-2:]) / len(VALUES_NUMERIC[-2:]), 2)
        assert state is not None
        assert state.state == str(new_mean)
        assert state.attributes.get("buffer_usage_ratio") == round(2 / 20, 2)
        assert state.attributes.get("age_coverage_ratio") == 1 / 4

        # Values expire over time. Only one is left

        current_time += timedelta(minutes=1)
        freezer.move_to(current_time)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test")
        new_mean = float(VALUES_NUMERIC[-1])
        assert state is not None
        assert state.state == str(new_mean)
        assert state.attributes.get("buffer_usage_ratio") == round(1 / 20, 2)
        assert state.attributes.get("age_coverage_ratio") == 0

        # Values expire over time. Buffer is empty

        current_time += timedelta(minutes=1)
        freezer.move_to(current_time)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test")
        assert state is not None
        assert state.state == STATE_UNKNOWN
        assert state.attributes.get("buffer_usage_ratio") == round(0 / 20, 2)
        assert state.attributes.get("age_coverage_ratio") is None


async def test_precision(hass: HomeAssistant) -> None:
    """Test correct results with precision set."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test_precision_0",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                    "precision": 0,
                },
                {
                    "platform": "statistics",
                    "name": "test_precision_3",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                    "precision": 3,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    for value in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        )
    await hass.async_block_till_done()

    mean = sum(VALUES_NUMERIC) / len(VALUES_NUMERIC)
    state = hass.states.get("sensor.test_precision_0")
    assert state is not None
    assert state.state == str(int(round(mean, 0)))
    state = hass.states.get("sensor.test_precision_3")
    assert state is not None
    assert state.state == str(round(mean, 3))


async def test_percentile(hass: HomeAssistant) -> None:
    """Test correct results for percentile characteristic."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test_percentile_omitted",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "percentile",
                    "sampling_size": 20,
                },
                {
                    "platform": "statistics",
                    "name": "test_percentile_default",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "percentile",
                    "sampling_size": 20,
                    "percentile": 50,
                },
                {
                    "platform": "statistics",
                    "name": "test_percentile_min",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "percentile",
                    "sampling_size": 20,
                    "percentile": 1,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    for value in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_percentile_omitted")
    assert state is not None
    assert state.state == str(9.2)
    state = hass.states.get("sensor.test_percentile_default")
    assert state is not None
    assert state.state == str(9.2)
    state = hass.states.get("sensor.test_percentile_min")
    assert state is not None
    assert state.state == str(2.72)


async def test_device_class(hass: HomeAssistant) -> None:
    """Test device class, which depends on the source entity."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    # Device class is carried over from source sensor for characteristics which retain unit
                    "platform": "statistics",
                    "name": "test_retain_unit",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                },
                {
                    # Device class is set to None for characteristics with special meaning
                    "platform": "statistics",
                    "name": "test_none",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "count",
                    "sampling_size": 20,
                },
                {
                    # Device class is set to timestamp for datetime characteristics
                    "platform": "statistics",
                    "name": "test_timestamp",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "datetime_oldest",
                    "sampling_size": 20,
                },
                {
                    # Device class is set to None for any source sensor with TOTAL state class
                    "platform": "statistics",
                    "name": "test_source_class_total",
                    "entity_id": "sensor.test_monitored_total",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    for value in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            {
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
            },
        )
        hass.states.async_set(
            "sensor.test_monitored_total",
            str(value),
            {
                ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.WATT_HOUR,
                ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
                ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            },
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_retain_unit")
    assert state is not None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    state = hass.states.get("sensor.test_none")
    assert state is not None
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    state = hass.states.get("sensor.test_timestamp")
    assert state is not None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    state = hass.states.get("sensor.test_source_class_total")
    assert state is not None
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None


async def test_state_class(hass: HomeAssistant) -> None:
    """Test state class, which depends on the characteristic configured."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    # State class is None for datetime characteristics
                    "platform": "statistics",
                    "name": "test_nan",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "datetime_oldest",
                    "sampling_size": 20,
                },
                {
                    # State class is MEASUREMENT for all other characteristics
                    "platform": "statistics",
                    "name": "test_normal",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "count",
                    "sampling_size": 20,
                },
                {
                    # State class is MEASUREMENT, even when the source sensor
                    # is of state class TOTAL
                    "platform": "statistics",
                    "name": "test_total",
                    "entity_id": "sensor.test_monitored_total",
                    "state_characteristic": "count",
                    "sampling_size": 20,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    for value in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        )
        hass.states.async_set(
            "sensor.test_monitored_total",
            str(value),
            {
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
                ATTR_STATE_CLASS: SensorStateClass.TOTAL,
            },
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_nan")
    assert state is not None
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    state = hass.states.get("sensor.test_normal")
    assert state is not None
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    state = hass.states.get("sensor.test_monitored_total")
    assert state is not None
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    state = hass.states.get("sensor.test_total")
    assert state is not None
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT


async def test_unitless_source_sensor(hass: HomeAssistant) -> None:
    """Statistics for a unitless source sensor should never have a unit."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test_unitless_1",
                    "entity_id": "sensor.test_monitored_unitless",
                    "state_characteristic": "count",
                    "sampling_size": 20,
                },
                {
                    "platform": "statistics",
                    "name": "test_unitless_2",
                    "entity_id": "sensor.test_monitored_unitless",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                },
                {
                    "platform": "statistics",
                    "name": "test_unitless_3",
                    "entity_id": "sensor.test_monitored_unitless",
                    "state_characteristic": "change_second",
                    "sampling_size": 20,
                },
                {
                    "platform": "statistics",
                    "name": "test_unitless_4",
                    "entity_id": "binary_sensor.test_monitored_unitless",
                    "state_characteristic": "count",
                    "sampling_size": 20,
                },
                {
                    "platform": "statistics",
                    "name": "test_unitless_5",
                    "entity_id": "binary_sensor.test_monitored_unitless",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    for value_numeric in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored_unitless",
            str(value_numeric),
        )
    for value_binary in VALUES_BINARY:
        hass.states.async_set(
            "binary_sensor.test_monitored_unitless",
            str(value_binary),
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_unitless_1")
    assert state and state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    state = hass.states.get("sensor.test_unitless_2")
    assert state and state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    state = hass.states.get("sensor.test_unitless_3")
    assert state and state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    state = hass.states.get("sensor.test_unitless_4")
    assert state and state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    state = hass.states.get("sensor.test_unitless_5")
    assert state and state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "%"


async def test_state_characteristics(hass: HomeAssistant) -> None:
    """Test configured state characteristic for value and unit."""
    now = dt_util.utcnow()
    current_time = datetime(now.year + 1, 8, 2, 12, 23, 42, tzinfo=dt_util.UTC)
    start_datetime = datetime(now.year + 1, 8, 2, 12, 23, 42, tzinfo=dt_util.UTC)
    characteristics: Sequence[dict[str, Any]] = (
        {
            "source_sensor_domain": "sensor",
            "name": "average_linear",
            "value_0": STATE_UNKNOWN,
            "value_1": STATE_UNKNOWN,
            "value_9": 10.68,
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "average_step",
            "value_0": STATE_UNKNOWN,
            "value_1": STATE_UNKNOWN,
            "value_9": 11.36,
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "average_timeless",
            "value_0": STATE_UNKNOWN,
            "value_1": float(VALUES_NUMERIC[-1]),
            "value_9": float(round(sum(VALUES_NUMERIC) / len(VALUES_NUMERIC), 2)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "change",
            "value_0": STATE_UNKNOWN,
            "value_1": float(0),
            "value_9": float(round(VALUES_NUMERIC[-1] - VALUES_NUMERIC[0], 2)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "change_sample",
            "value_0": STATE_UNKNOWN,
            "value_1": STATE_UNKNOWN,
            "value_9": float(
                round(
                    (VALUES_NUMERIC[-1] - VALUES_NUMERIC[0])
                    / (len(VALUES_NUMERIC) - 1),
                    2,
                )
            ),
            "unit": "°C/sample",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "change_second",
            "value_0": STATE_UNKNOWN,
            "value_1": STATE_UNKNOWN,
            "value_9": float(
                round(
                    (VALUES_NUMERIC[-1] - VALUES_NUMERIC[0])
                    / (60 * (len(VALUES_NUMERIC) - 1)),
                    2,
                )
            ),
            "unit": "°C/s",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "count",
            "value_0": 0,
            "value_1": 1,
            "value_9": 9,
            "unit": None,
        },
        {
            "source_sensor_domain": "sensor",
            "name": "datetime_newest",
            "value_0": STATE_UNKNOWN,
            "value_1": (start_datetime + timedelta(minutes=9)).isoformat(),
            "value_9": (start_datetime + timedelta(minutes=9)).isoformat(),
            "unit": None,
        },
        {
            "source_sensor_domain": "sensor",
            "name": "datetime_oldest",
            "value_0": STATE_UNKNOWN,
            "value_1": (start_datetime + timedelta(minutes=9)).isoformat(),
            "value_9": (start_datetime + timedelta(minutes=1)).isoformat(),
            "unit": None,
        },
        {
            "source_sensor_domain": "sensor",
            "name": "datetime_value_max",
            "value_0": STATE_UNKNOWN,
            "value_1": (start_datetime + timedelta(minutes=9)).isoformat(),
            "value_9": (start_datetime + timedelta(minutes=2)).isoformat(),
            "unit": None,
        },
        {
            "source_sensor_domain": "sensor",
            "name": "datetime_value_min",
            "value_0": STATE_UNKNOWN,
            "value_1": (start_datetime + timedelta(minutes=9)).isoformat(),
            "value_9": (start_datetime + timedelta(minutes=5)).isoformat(),
            "unit": None,
        },
        {
            "source_sensor_domain": "sensor",
            "name": "distance_95_percent_of_values",
            "value_0": STATE_UNKNOWN,
            "value_1": STATE_UNKNOWN,
            "value_9": float(round(2 * 1.96 * statistics.stdev(VALUES_NUMERIC), 2)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "distance_99_percent_of_values",
            "value_0": STATE_UNKNOWN,
            "value_1": STATE_UNKNOWN,
            "value_9": float(round(2 * 2.58 * statistics.stdev(VALUES_NUMERIC), 2)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "distance_absolute",
            "value_0": STATE_UNKNOWN,
            "value_1": float(0),
            "value_9": float(max(VALUES_NUMERIC) - min(VALUES_NUMERIC)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "mean",
            "value_0": STATE_UNKNOWN,
            "value_1": float(VALUES_NUMERIC[-1]),
            "value_9": float(round(sum(VALUES_NUMERIC) / len(VALUES_NUMERIC), 2)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "mean_circular",
            "value_0": STATE_UNKNOWN,
            "value_1": float(VALUES_NUMERIC[-1]),
            "value_9": 10.76,
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "median",
            "value_0": STATE_UNKNOWN,
            "value_1": float(VALUES_NUMERIC[-1]),
            "value_9": float(round(statistics.median(VALUES_NUMERIC), 2)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "noisiness",
            "value_0": STATE_UNKNOWN,
            "value_1": STATE_UNKNOWN,
            "value_9": float(round(sum([3, 4.8, 10.2, 1.2, 5.4, 2.5, 7.3, 8]) / 8, 2)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "percentile",
            "value_0": STATE_UNKNOWN,
            "value_1": STATE_UNKNOWN,
            "value_9": 9.2,
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "standard_deviation",
            "value_0": STATE_UNKNOWN,
            "value_1": STATE_UNKNOWN,
            "value_9": float(round(statistics.stdev(VALUES_NUMERIC), 2)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "sum",
            "value_0": STATE_UNKNOWN,
            "value_1": float(VALUES_NUMERIC[-1]),
            "value_9": float(sum(VALUES_NUMERIC)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "sum_differences",
            "value_0": STATE_UNKNOWN,
            "value_1": STATE_UNKNOWN,
            "value_9": float(
                sum(
                    [
                        abs(20 - 17),
                        abs(15.2 - 20),
                        abs(5 - 15.2),
                        abs(3.8 - 5),
                        abs(9.2 - 3.8),
                        abs(6.7 - 9.2),
                        abs(14 - 6.7),
                        abs(6 - 14),
                    ]
                )
            ),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "sum_differences_nonnegative",
            "value_0": STATE_UNKNOWN,
            "value_1": STATE_UNKNOWN,
            "value_9": float(
                sum(
                    [
                        20 - 17,
                        15.2 - 0,
                        5 - 0,
                        3.8 - 0,
                        9.2 - 3.8,
                        6.7 - 0,
                        14 - 6.7,
                        6 - 0,
                    ]
                )
            ),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "total",
            "value_0": STATE_UNKNOWN,
            "value_1": float(VALUES_NUMERIC[-1]),
            "value_9": float(sum(VALUES_NUMERIC)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "value_max",
            "value_0": STATE_UNKNOWN,
            "value_1": float(VALUES_NUMERIC[-1]),
            "value_9": float(max(VALUES_NUMERIC)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "value_min",
            "value_0": STATE_UNKNOWN,
            "value_1": float(VALUES_NUMERIC[-1]),
            "value_9": float(min(VALUES_NUMERIC)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "variance",
            "value_0": STATE_UNKNOWN,
            "value_1": STATE_UNKNOWN,
            "value_9": float(round(statistics.variance(VALUES_NUMERIC), 2)),
            "unit": "°C²",
        },
        {
            "source_sensor_domain": "binary_sensor",
            "name": "average_step",
            "value_0": STATE_UNKNOWN,
            "value_1": STATE_UNKNOWN,
            "value_9": 50.0,
            "unit": "%",
        },
        {
            "source_sensor_domain": "binary_sensor",
            "name": "average_timeless",
            "value_0": STATE_UNKNOWN,
            "value_1": 100.0,
            "value_9": float(
                round(100 / len(VALUES_BINARY) * VALUES_BINARY.count("on"), 2)
            ),
            "unit": "%",
        },
        {
            "source_sensor_domain": "binary_sensor",
            "name": "count",
            "value_0": 0,
            "value_1": 1,
            "value_9": len(VALUES_BINARY),
            "unit": None,
        },
        {
            "source_sensor_domain": "binary_sensor",
            "name": "count_on",
            "value_0": 0,
            "value_1": 1,
            "value_9": VALUES_BINARY.count("on"),
            "unit": None,
        },
        {
            "source_sensor_domain": "binary_sensor",
            "name": "count_off",
            "value_0": 0,
            "value_1": 0,
            "value_9": VALUES_BINARY.count("off"),
            "unit": None,
        },
        {
            "source_sensor_domain": "binary_sensor",
            "name": "datetime_newest",
            "value_0": STATE_UNKNOWN,
            "value_1": (start_datetime + timedelta(minutes=9)).isoformat(),
            "value_9": (start_datetime + timedelta(minutes=9)).isoformat(),
            "unit": None,
        },
        {
            "source_sensor_domain": "binary_sensor",
            "name": "datetime_oldest",
            "value_0": STATE_UNKNOWN,
            "value_1": (start_datetime + timedelta(minutes=9)).isoformat(),
            "value_9": (start_datetime + timedelta(minutes=1)).isoformat(),
            "unit": None,
        },
        {
            "source_sensor_domain": "binary_sensor",
            "name": "mean",
            "value_0": STATE_UNKNOWN,
            "value_1": 100.0,
            "value_9": float(
                round(100 / len(VALUES_BINARY) * VALUES_BINARY.count("on"), 2)
            ),
            "unit": "%",
        },
    )
    sensors_config = []
    for characteristic in characteristics:
        sensors_config.append(
            {
                "platform": "statistics",
                "name": f"test_{characteristic['source_sensor_domain']}_{characteristic['name']}",
                "entity_id": f"{characteristic['source_sensor_domain']}.test_monitored",
                "state_characteristic": characteristic["name"],
                "max_age": {"minutes": 8},  # 9 values spaces by one minute
            }
        )

    with freeze_time(current_time) as freezer:
        assert await async_setup_component(
            hass,
            "sensor",
            {"sensor": sensors_config},
        )
        await hass.async_block_till_done()

        # With all values in buffer

        for i in range(len(VALUES_NUMERIC)):
            current_time += timedelta(minutes=1)
            freezer.move_to(current_time)
            async_fire_time_changed(hass, current_time)
            hass.states.async_set(
                "sensor.test_monitored",
                str(VALUES_NUMERIC[i]),
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
            )
            hass.states.async_set(
                "binary_sensor.test_monitored",
                str(VALUES_BINARY[i]),
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
            )
        await hass.async_block_till_done()

        for characteristic in characteristics:
            state = hass.states.get(
                f"sensor.test_{characteristic['source_sensor_domain']}_{characteristic['name']}"
            )
            assert state is not None, (
                "no state object for characteristic "
                f"'{characteristic['source_sensor_domain']}/{characteristic['name']}' "
                "(buffer filled)"
            )
            assert state.state == str(characteristic["value_9"]), (
                "value mismatch for characteristic "
                f"'{characteristic['source_sensor_domain']}/{characteristic['name']}' "
                "(buffer filled) - "
                f"assert {state.state} == {str(characteristic['value_9'])}"
            )
            assert (
                state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == characteristic["unit"]
            ), f"unit mismatch for characteristic '{characteristic['name']}'"

        # With single value in buffer

        current_time += timedelta(minutes=8)
        freezer.move_to(current_time)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()

        for characteristic in characteristics:
            state = hass.states.get(
                f"sensor.test_{characteristic['source_sensor_domain']}_{characteristic['name']}"
            )
            assert state is not None, (
                "no state object for characteristic "
                f"'{characteristic['source_sensor_domain']}/{characteristic['name']}' "
                "(one stored value)"
            )
            assert state.state == str(characteristic["value_1"]), (
                "value mismatch for characteristic "
                f"'{characteristic['source_sensor_domain']}/{characteristic['name']}' "
                "(one stored value) - "
                f"assert {state.state} == {str(characteristic['value_1'])}"
            )

        # With empty buffer

        current_time += timedelta(minutes=1)
        freezer.move_to(current_time)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()

        for characteristic in characteristics:
            state = hass.states.get(
                f"sensor.test_{characteristic['source_sensor_domain']}_{characteristic['name']}"
            )
            assert state is not None, (
                "no state object for characteristic "
                f"'{characteristic['source_sensor_domain']}/{characteristic['name']}' "
                "(buffer empty)"
            )
            assert state.state == str(characteristic["value_0"]), (
                "value mismatch for characteristic "
                f"'{characteristic['source_sensor_domain']}/{characteristic['name']}' "
                "(buffer empty) - "
                f"assert {state.state} == {str(characteristic['value_0'])}"
            )


async def test_state_characteristic_mean_circular(hass: HomeAssistant) -> None:
    """Test the mean_circular state characteristic using angle data."""
    values_angular = [0, 10, 90.5, 180, 269.5, 350]

    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test_sensor_mean_circular",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean_circular",
                    "sampling_size": 6,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    for angle in values_angular:
        hass.states.async_set(
            "sensor.test_monitored",
            str(angle),
            {ATTR_UNIT_OF_MEASUREMENT: DEGREE},
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sensor_mean_circular")
    assert state is not None
    assert state.state == "0.0", (
        "value mismatch for characteristic 'sensor/mean_circular' - "
        f"assert {state.state} == 0.0"
    )


async def test_invalid_state_characteristic(hass: HomeAssistant) -> None:
    """Test the detection of wrong state_characteristics selected."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test_numeric",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "invalid",
                    "sampling_size": 20,
                },
                {
                    "platform": "statistics",
                    "name": "test_binary",
                    "entity_id": "binary_sensor.test_monitored",
                    "state_characteristic": "variance",
                    "sampling_size": 20,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "sensor.test_monitored",
        str(VALUES_NUMERIC[0]),
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_numeric")
    assert state is None
    state = hass.states.get("sensor.test_binary")
    assert state is None


async def test_initialize_from_database(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test initializing the statistics from the recorder database."""
    # enable and pre-fill the recorder
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    for value in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        )
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    # create the statistics component, get filled from database
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "sampling_size": 100,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert state is not None
    assert state.state == str(round(sum(VALUES_NUMERIC) / len(VALUES_NUMERIC), 2))
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS


@pytest.mark.freeze_time(
    datetime(dt_util.utcnow().year + 1, 8, 2, 12, 23, 42, tzinfo=dt_util.UTC)
)
async def test_initialize_from_database_with_maxage(
    recorder_mock: Recorder, hass: HomeAssistant
) -> None:
    """Test initializing the statistics from the database."""
    current_time = dt_util.utcnow()

    # Testing correct retrieval from recorder, thus we do not
    # want purging to occur within the class itself.
    def mock_purge(self, *args):
        return

    # enable and pre-fill the recorder
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    with freeze_time(current_time) as freezer, patch.object(
        StatisticsSensor, "_purge_old_states", mock_purge
    ):
        for value in VALUES_NUMERIC:
            hass.states.async_set(
                "sensor.test_monitored",
                str(value),
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
            )
            await hass.async_block_till_done()
            current_time += timedelta(hours=1)
            freezer.move_to(current_time)

        await async_wait_recording_done(hass)
        # create the statistics component, get filled from database
        assert await async_setup_component(
            hass,
            "sensor",
            {
                "sensor": [
                    {
                        "platform": "statistics",
                        "name": "test",
                        "entity_id": "sensor.test_monitored",
                        "state_characteristic": "datetime_newest",
                        "sampling_size": 100,
                        "max_age": {"hours": 3},
                    },
                ]
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert state is not None
    assert state.attributes.get("age_coverage_ratio") == round(2 / 3, 2)
    # The max_age timestamp should be 1 hour before what we have right
    # now in mock_data['return_time'].
    assert current_time == datetime.strptime(
        state.state, "%Y-%m-%dT%H:%M:%S%z"
    ) + timedelta(hours=1)


async def test_reload(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Verify we can reload statistics sensors."""

    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "sampling_size": 100,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", "0")
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("sensor.test")

    yaml_path = get_fixture_path("configuration.yaml", "statistics")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            STATISTICS_DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("sensor.test") is None
    assert hass.states.get("sensor.cputest")
