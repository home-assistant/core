"""The test for the statistics sensor platform."""

from __future__ import annotations

from asyncio import Event as AsyncioEvent
from collections.abc import Sequence
from datetime import datetime, timedelta
import statistics
from threading import Event as ThreadingEvent
from typing import Any
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant import config as hass_config
from homeassistant.components.recorder import Recorder, history
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.statistics import DOMAIN
from homeassistant.components.statistics.sensor import (
    CONF_KEEP_LAST_SAMPLE,
    CONF_PERCENTILE,
    CONF_PRECISION,
    CONF_SAMPLES_MAX_BUFFER_SIZE,
    CONF_STATE_CHARACTERISTIC,
    STAT_MEAN,
    StatisticsSensor,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_ID,
    CONF_NAME,
    DEGREE,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfTemperature,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, get_fixture_path
from tests.components.recorder.common import async_wait_recording_done

VALUES_BINARY = ["on", "off", "on", "off", "on", "off", "on", "off", "on"]
VALUES_NUMERIC = [17, 20, 15.2, 5, 3.8, 9.2, 6.7, 14, 6]
VALUES_NUMERIC_LINEAR = [1, 2, 3, 4, 5, 6, 7, 8, 9]

A1 = {"attr": "value1"}
A2 = {"attr": "value2"}


async def test_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
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

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "uniqueid_sensor_test"
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


@pytest.mark.parametrize(
    "get_config",
    [
        {
            CONF_NAME: "test",
            CONF_ENTITY_ID: "sensor.test_monitored",
            CONF_STATE_CHARACTERISTIC: STAT_MEAN,
            CONF_SAMPLES_MAX_BUFFER_SIZE: 20.0,
            CONF_KEEP_LAST_SAMPLE: False,
            CONF_PERCENTILE: 50.0,
            CONF_PRECISION: 2.0,
        }
    ],
)
async def test_sensor_loaded_from_config_entry(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test the sensor loaded from a config entry."""

    state = hass.states.get("sensor.test")
    assert state is not None
    assert state.state == str(round(sum(VALUES_NUMERIC) / len(VALUES_NUMERIC), 2))
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    assert state.attributes.get("buffer_usage_ratio") == round(9 / 20, 2)
    assert state.attributes.get("source_value_valid") is True
    assert "age_coverage_ratio" not in state.attributes


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


@pytest.mark.parametrize("force_update", [True, False])
@pytest.mark.parametrize(
    ("values", "attributes"),
    [
        # Fires last reported events
        ([18, 1, 1, 1, 1, 1, 1, 1, 9], [A1, A1, A1, A1, A1, A1, A1, A1, A1]),
        # Fires state change events
        ([18, 1, 1, 1, 1, 1, 1, 1, 9], [A1, A2, A1, A2, A1, A2, A1, A2, A1]),
    ],
)
async def test_sensor_state_updated_reported(
    hass: HomeAssistant,
    values: list[float],
    attributes: list[dict[str, Any]],
    force_update: bool,
) -> None:
    """Test the behavior of the sensor with a sequence of identical values.

    Forced updates no longer make a difference, since the statistics are now reacting not
    only to state change events but also to state report events (EVENT_STATE_REPORTED).
    This means repeating values will be added to the buffer repeatedly in both cases.
    This fixes problems with time based averages and some other functions that behave
    differently when repeating values are reported.
    """
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test_normal",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    for value, attribute in zip(values, attributes, strict=True):
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS} | attribute,
            force_update=force_update,
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_normal")
    assert state
    assert state.state == str(round(sum(values) / 9, 2))
    assert state.attributes.get("buffer_usage_ratio") == round(9 / 20, 2)


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


async def test_keep_last_value_given(hass: HomeAssistant) -> None:
    """Test if either sampling_size or max_age are given."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "statistics",
                    "name": "test_none",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "keep_last_sample": True,
                },
                {
                    "platform": "statistics",
                    "name": "test_sampling_size",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                    "keep_last_sample": True,
                },
                {
                    "platform": "statistics",
                    "name": "test_max_age",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "max_age": {"minutes": 4},
                    "keep_last_sample": True,
                },
                {
                    "platform": "statistics",
                    "name": "test_both",
                    "entity_id": "sensor.test_monitored",
                    "state_characteristic": "mean",
                    "sampling_size": 20,
                    "max_age": {"minutes": 4},
                    "keep_last_sample": True,
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

    state = hass.states.get("sensor.test_none")
    assert state is None
    state = hass.states.get("sensor.test_sampling_size")
    assert state is None
    state = hass.states.get("sensor.test_max_age")
    assert state is not None
    state = hass.states.get("sensor.test_both")
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
        assert state.attributes.get("age_coverage_ratio") == 0


async def test_age_limit_expiry_with_keep_last_sample(hass: HomeAssistant) -> None:
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
                        "keep_last_sample": True,
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

        # Values expire over time. All values expired, but preserve expired last value

        current_time += timedelta(minutes=1)
        freezer.move_to(current_time)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test")
        assert state is not None
        assert state.state == str(float(VALUES_NUMERIC[-1]))
        assert state.attributes.get("buffer_usage_ratio") == round(1 / 20, 2)
        assert state.attributes.get("age_coverage_ratio") == 0

        # Indefinitely preserve expired last value

        current_time += timedelta(minutes=1)
        freezer.move_to(current_time)
        async_fire_time_changed(hass, current_time)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test")
        assert state is not None
        assert state.state == str(float(VALUES_NUMERIC[-1]))
        assert state.attributes.get("buffer_usage_ratio") == round(1 / 20, 2)
        assert state.attributes.get("age_coverage_ratio") == 0

        # New sensor value within max_age, preserved expired value should be dropped
        last_update_val = 123.0
        current_time += timedelta(minutes=1)
        freezer.move_to(current_time)
        async_fire_time_changed(hass, current_time)
        hass.states.async_set(
            "sensor.test_monitored",
            str(last_update_val),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        )
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test")
        assert state is not None
        assert state.state == str(last_update_val)
        assert state.attributes.get("buffer_usage_ratio") == round(1 / 20, 2)
        assert state.attributes.get("age_coverage_ratio") == 0


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
            "value_1": 6.0,
            "value_9": 10.68,
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "average_step",
            "value_0": STATE_UNKNOWN,
            "value_1": 6.0,
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
            "value_1": 0.0,
            "value_9": float(round(2 * 1.96 * statistics.stdev(VALUES_NUMERIC), 2)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "distance_99_percent_of_values",
            "value_0": STATE_UNKNOWN,
            "value_1": 0.0,
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
            "value_1": 0.0,
            "value_9": float(round(sum([3, 4.8, 10.2, 1.2, 5.4, 2.5, 7.3, 8]) / 8, 2)),
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "percentile",
            "value_0": STATE_UNKNOWN,
            "value_1": 6.0,
            "value_9": 9.2,
            "unit": "°C",
        },
        {
            "source_sensor_domain": "sensor",
            "name": "standard_deviation",
            "value_0": STATE_UNKNOWN,
            "value_1": 0.0,
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
            "value_1": 0.0,
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
            "value_1": 0.0,
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
            "value_1": 0.0,
            "value_9": float(round(statistics.variance(VALUES_NUMERIC), 2)),
            "unit": "°C²",
        },
        {
            "source_sensor_domain": "binary_sensor",
            "name": "average_step",
            "value_0": STATE_UNKNOWN,
            "value_1": 100.0,
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
    sensors_config = [
        {
            "platform": "statistics",
            "name": f"test_{characteristic['source_sensor_domain']}_{characteristic['name']}",
            "entity_id": f"{characteristic['source_sensor_domain']}.test_monitored",
            "state_characteristic": characteristic["name"],
            "max_age": {"minutes": 8},  # 9 values spaces by one minute
        }
        for characteristic in characteristics
    ]

    with freeze_time(current_time) as freezer:
        assert await async_setup_component(
            hass,
            "sensor",
            {"sensor": sensors_config},
        )
        await hass.async_block_till_done()

        # With all values in buffer

        for i, value in enumerate(VALUES_NUMERIC):
            current_time += timedelta(minutes=1)
            freezer.move_to(current_time)
            async_fire_time_changed(hass, current_time)
            hass.states.async_set(
                "sensor.test_monitored",
                str(value),
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
                f"assert {state.state} == {characteristic['value_9']!s}"
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
                f"assert {state.state} == {characteristic['value_1']!s}"
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
                f"assert {state.state} == {characteristic['value_0']!s}"
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

    with (
        freeze_time(current_time) as freezer,
        patch.object(StatisticsSensor, "_purge_old_states", mock_purge),
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
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("sensor.test") is None
    assert hass.states.get("sensor.cputest")


async def test_device_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test for source entity device for Statistics."""
    source_config_entry = MockConfigEntry()
    source_config_entry.add_to_hass(hass)
    source_device_entry = device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        identifiers={("sensor", "identifier_test")},
        connections={("mac", "30:31:32:33:34:35")},
    )
    source_entity = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source",
        config_entry=source_config_entry,
        device_id=source_device_entry.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.test_source") is not None

    statistics_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "Statistics",
            "entity_id": "sensor.test_source",
            "state_characteristic": "mean",
            "keep_last_sample": False,
            "percentile": 50.0,
            "precision": 2.0,
            "sampling_size": 20.0,
        },
        title="Statistics",
    )
    statistics_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(statistics_config_entry.entry_id)
    await hass.async_block_till_done()

    statistics_entity = entity_registry.async_get("sensor.statistics")
    assert statistics_entity is not None
    assert statistics_entity.device_id == source_entity.device_id


async def test_update_before_load(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Verify that updates happening before reloading from the database are handled correctly."""

    current_time = dt_util.utcnow()

    # enable and pre-fill the recorder
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    with (
        freeze_time(current_time) as freezer,
    ):
        for value in VALUES_NUMERIC_LINEAR:
            hass.states.async_set(
                "sensor.test_monitored",
                str(value),
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
            )
            await hass.async_block_till_done()
            current_time += timedelta(seconds=1)
            freezer.move_to(current_time)

        await async_wait_recording_done(hass)

        # some synchronisation is needed to prevent that loading from the database finishes too soon
        # we want this to take long enough to be able to try to add a value BEFORE loading is done
        state_changes_during_period_called_evt = AsyncioEvent()
        state_changes_during_period_stall_evt = ThreadingEvent()
        real_state_changes_during_period = history.state_changes_during_period

        def mock_state_changes_during_period(*args, **kwargs):
            states = real_state_changes_during_period(*args, **kwargs)
            hass.loop.call_soon_threadsafe(state_changes_during_period_called_evt.set)
            state_changes_during_period_stall_evt.wait()
            return states

        # create the statistics component, get filled from database
        with patch(
            "homeassistant.components.statistics.sensor.history.state_changes_during_period",
            mock_state_changes_during_period,
        ):
            assert await async_setup_component(
                hass,
                "sensor",
                {
                    "sensor": [
                        {
                            "platform": "statistics",
                            "name": "test",
                            "entity_id": "sensor.test_monitored",
                            "state_characteristic": "average_step",
                            "max_age": {"seconds": 10},
                        },
                    ]
                },
            )
            # adding this value is going to be ignored, since loading from the database hasn't finished yet
            # if this value would be added before loading from the database is done
            # it would mess up the order of the internal queue which is supposed to be sorted by time
            await state_changes_during_period_called_evt.wait()
            hass.states.async_set(
                "sensor.test_monitored",
                "10",
                {ATTR_UNIT_OF_MEASUREMENT: DEGREE},
            )
            state_changes_during_period_stall_evt.set()
            await hass.async_block_till_done()

    # we will end up with a buffer of [1 .. 9] (10 wasn't added)
    # so the computed average_step is 1+2+3+4+5+6+7+8/8 = 4.5
    assert float(hass.states.get("sensor.test").state) == pytest.approx(4.5)


@pytest.mark.parametrize("force_update", [True, False])
@pytest.mark.parametrize(
    ("values_attributes_and_times", "expected_states"),
    [
        (
            # Fires last reported events
            [(5.0, A1, 2), (10.0, A1, 1), (10.0, A1, 1), (10.0, A1, 2), (5.0, A1, 1)],
            ["unavailable", "5.0", "7.5", "8.33", "8.75", "8.33"],
        ),
        (  # Fires state change events
            [(5.0, A1, 2), (10.0, A2, 1), (10.0, A1, 1), (10.0, A2, 2), (5.0, A1, 1)],
            ["unavailable", "5.0", "7.5", "8.33", "8.75", "8.33"],
        ),
        (
            # Fires last reported events
            [(10.0, A1, 2), (10.0, A1, 1), (10.0, A1, 1), (10.0, A1, 2), (10.0, A1, 1)],
            ["unavailable", "10.0", "10.0", "10.0", "10.0", "10.0"],
        ),
        (  # Fires state change events
            [(10.0, A1, 2), (10.0, A2, 1), (10.0, A1, 1), (10.0, A2, 2), (10.0, A1, 1)],
            ["unavailable", "10.0", "10.0", "10.0", "10.0", "10.0"],
        ),
    ],
)
async def test_average_linear_unevenly_timed(
    hass: HomeAssistant,
    force_update: bool,
    values_attributes_and_times: list[tuple[float, dict[str, Any], float]],
    expected_states: list[str],
) -> None:
    """Test the average_linear state characteristic with unevenly distributed values.

    This also implicitly tests the correct timing of repeating values.
    """
    events: list[Event[EventStateChangedData]] = []

    @callback
    def _capture_event(event: Event) -> None:
        events.append(event)

    async_track_state_change_event(
        hass, "sensor.test_sensor_average_linear", _capture_event
    )

    current_time = dt_util.utcnow()

    with (
        freeze_time(current_time) as freezer,
    ):
        assert await async_setup_component(
            hass,
            "sensor",
            {
                "sensor": [
                    {
                        "platform": "statistics",
                        "name": "test_sensor_average_linear",
                        "entity_id": "sensor.test_monitored",
                        "state_characteristic": "average_linear",
                        "max_age": {"seconds": 10},
                    },
                ]
            },
        )
        await hass.async_block_till_done()

        for value, extra_attributes, time in values_attributes_and_times:
            hass.states.async_set(
                "sensor.test_monitored",
                str(value),
                {ATTR_UNIT_OF_MEASUREMENT: DEGREE} | extra_attributes,
                force_update=force_update,
            )
            current_time += timedelta(seconds=time)
            freezer.move_to(current_time)

        await hass.async_block_till_done()

    await hass.async_block_till_done()
    assert [event.data["new_state"].state for event in events] == expected_states


async def test_sensor_unit_gets_removed(hass: HomeAssistant) -> None:
    """Test when input lose its unit of measurement."""
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
                    "sampling_size": 10,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    input_attributes = {
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
    }

    for value in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            input_attributes,
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert state is not None
    assert state.state == str(round(sum(VALUES_NUMERIC) / len(VALUES_NUMERIC), 2))
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    hass.states.async_set(
        "sensor.test_monitored",
        str(VALUES_NUMERIC[0]),
        {
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert state is not None
    assert state.state == "11.39"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    # Temperature device class is not valid with no unit of measurement
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    for value in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            input_attributes,
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert state is not None
    assert state.state == "11.39"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT


async def test_sensor_device_class_gets_removed(hass: HomeAssistant) -> None:
    """Test when device class gets removed."""
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
                    "sampling_size": 10,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    input_attributes = {
        ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
        ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
    }

    for value in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            input_attributes,
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert state is not None
    assert state.state == str(round(sum(VALUES_NUMERIC) / len(VALUES_NUMERIC), 2))
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    hass.states.async_set(
        "sensor.test_monitored",
        str(VALUES_NUMERIC[0]),
        {
            ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert state is not None
    assert state.state == "11.39"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    for value in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            input_attributes,
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert state is not None
    assert state.state == "11.39"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT


async def test_not_valid_device_class(hass: HomeAssistant) -> None:
    """Test when not valid device class."""
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
                    "sampling_size": 10,
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
                ATTR_DEVICE_CLASS: SensorDeviceClass.DATE,
            },
        )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert state is not None
    assert state.state == str(round(sum(VALUES_NUMERIC) / len(VALUES_NUMERIC), 2))
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    hass.states.async_set(
        "sensor.test_monitored",
        str(10),
        {
            ATTR_DEVICE_CLASS: "not_exist",
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")
    assert state is not None
    assert state.state == "10.69"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT


async def test_attributes_remains(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Test attributes are always present."""
    for value in VALUES_NUMERIC:
        hass.states.async_set(
            "sensor.test_monitored",
            str(value),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        )
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    current_time = dt_util.utcnow()
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
                        "max_age": {"seconds": 10},
                    },
                ]
            },
        )
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test")
        assert state is not None
        assert state.state == str(round(sum(VALUES_NUMERIC) / len(VALUES_NUMERIC), 2))
        assert state.attributes == {
            "age_coverage_ratio": 0.0,
            "friendly_name": "test",
            "icon": "mdi:calculator",
            "source_value_valid": True,
            "state_class": SensorStateClass.MEASUREMENT,
            "unit_of_measurement": "°C",
        }

        freezer.move_to(current_time + timedelta(minutes=1))
        async_fire_time_changed(hass)

        state = hass.states.get("sensor.test")
        assert state is not None
        assert state.state == STATE_UNKNOWN
        assert state.attributes == {
            "age_coverage_ratio": 0,
            "friendly_name": "test",
            "icon": "mdi:calculator",
            "source_value_valid": True,
            "state_class": SensorStateClass.MEASUREMENT,
            "unit_of_measurement": "°C",
        }
