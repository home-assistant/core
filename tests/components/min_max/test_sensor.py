"""The test for the min/max sensor platform."""

import statistics
from unittest.mock import patch

import pytest

from homeassistant import config as hass_config
from homeassistant.components.min_max.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path

VALUES = [17, 20, 15.3]
VALUES_ERROR = [17, "string", 15.3]
COUNT = len(VALUES)
MIN_VALUE = min(VALUES)
MAX_VALUE = max(VALUES)
MEAN = round(sum(VALUES) / COUNT, 2)
MEAN_1_DIGIT = round(sum(VALUES) / COUNT, 1)
MEAN_4_DIGITS = round(sum(VALUES) / COUNT, 4)
MEDIAN = round(statistics.median(VALUES), 2)
RANGE_1_DIGIT = round(max(VALUES) - min(VALUES), 1)
RANGE_4_DIGITS = round(max(VALUES) - min(VALUES), 4)
SUM_VALUE = sum(VALUES)


async def test_default_name_sensor(hass: HomeAssistant) -> None:
    """Test the min sensor with a default name."""
    config = {
        "sensor": {
            "platform": "min_max",
            "type": "min",
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.min_sensor")

    assert str(float(MIN_VALUE)) == state.state
    assert entity_ids[2] == state.attributes.get("min_entity_id")


async def test_min_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the min sensor."""
    config = {
        "sensor": {
            "platform": "min_max",
            "name": "test_min",
            "type": "min",
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_min")

    assert str(float(MIN_VALUE)) == state.state
    assert entity_ids[2] == state.attributes.get("min_entity_id")
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entity = entity_registry.async_get("sensor.test_min")
    assert entity.unique_id == "very_unique_id"


async def test_max_sensor(hass: HomeAssistant) -> None:
    """Test the max sensor."""
    config = {
        "sensor": {
            "platform": "min_max",
            "name": "test_max",
            "type": "max",
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_max")

    assert str(float(MAX_VALUE)) == state.state
    assert entity_ids[1] == state.attributes.get("max_entity_id")
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT


async def test_mean_sensor(hass: HomeAssistant) -> None:
    """Test the mean sensor."""
    config = {
        "sensor": {
            "platform": "min_max",
            "name": "test_mean",
            "type": "mean",
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_mean")

    assert str(float(MEAN)) == state.state
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT


async def test_mean_1_digit_sensor(hass: HomeAssistant) -> None:
    """Test the mean with 1-digit precision sensor."""
    config = {
        "sensor": {
            "platform": "min_max",
            "name": "test_mean",
            "type": "mean",
            "round_digits": 1,
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_mean")

    assert str(float(MEAN_1_DIGIT)) == state.state


async def test_mean_4_digit_sensor(hass: HomeAssistant) -> None:
    """Test the mean with 4-digit precision sensor."""
    config = {
        "sensor": {
            "platform": "min_max",
            "name": "test_mean",
            "type": "mean",
            "round_digits": 4,
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_mean")

    assert str(float(MEAN_4_DIGITS)) == state.state


async def test_median_sensor(hass: HomeAssistant) -> None:
    """Test the median sensor."""
    config = {
        "sensor": {
            "platform": "min_max",
            "name": "test_median",
            "type": "median",
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_median")

    assert str(float(MEDIAN)) == state.state
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT


async def test_range_4_digit_sensor(hass: HomeAssistant) -> None:
    """Test the range with 4-digit precision sensor."""
    config = {
        "sensor": {
            "platform": "min_max",
            "name": "test_range",
            "type": "range",
            "round_digits": 4,
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_range")

    assert str(float(RANGE_4_DIGITS)) == state.state


async def test_range_1_digit_sensor(hass: HomeAssistant) -> None:
    """Test the range with 1-digit precision sensor."""
    config = {
        "sensor": {
            "platform": "min_max",
            "name": "test_range",
            "type": "range",
            "round_digits": 1,
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_range")

    assert str(float(RANGE_1_DIGIT)) == state.state


async def test_not_enough_sensor_value(hass: HomeAssistant) -> None:
    """Test that there is nothing done if not enough values available."""
    config = {
        "sensor": {
            "platform": "min_max",
            "name": "test_max",
            "type": "max",
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    hass.states.async_set(entity_ids[0], STATE_UNKNOWN)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_max")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("min_entity_id") is None
    assert state.attributes.get("min_value") is None
    assert state.attributes.get("max_entity_id") is None
    assert state.attributes.get("max_value") is None
    assert state.attributes.get("median") is None

    hass.states.async_set(entity_ids[1], VALUES[1])
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_max")
    assert state.state != STATE_UNKNOWN
    assert entity_ids[1] == state.attributes.get("max_entity_id")

    hass.states.async_set(entity_ids[2], STATE_UNKNOWN)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_max")
    assert state.state != STATE_UNKNOWN
    assert entity_ids[1] == state.attributes.get("max_entity_id")

    hass.states.async_set(entity_ids[1], STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_max")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("min_entity_id") is None
    assert state.attributes.get("min_value") is None
    assert state.attributes.get("max_entity_id") is None
    assert state.attributes.get("max_value") is None


async def test_different_unit_of_measurement(hass: HomeAssistant) -> None:
    """Test for different unit of measurement."""
    config = {
        "sensor": {
            "platform": "min_max",
            "name": "test",
            "type": "mean",
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    hass.states.async_set(
        entity_ids[0], VALUES[0], {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS}
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")

    assert str(float(VALUES[0])) == state.state
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.CELSIUS

    hass.states.async_set(
        entity_ids[1],
        VALUES[1],
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")

    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("unit_of_measurement") == "ERR"

    hass.states.async_set(
        entity_ids[2], VALUES[2], {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE}
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test")

    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("unit_of_measurement") == "ERR"


async def test_last_sensor(hass: HomeAssistant) -> None:
    """Test the last sensor."""
    config = {
        "sensor": {
            "platform": "min_max",
            "name": "test_last",
            "type": "last",
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test_last")
        assert str(float(value)) == state.state
        assert entity_id == state.attributes.get("last_entity_id")
        assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT


async def test_reload(hass: HomeAssistant) -> None:
    """Verify we can reload filter sensors."""
    hass.states.async_set("sensor.test_1", 12345)
    hass.states.async_set("sensor.test_2", 45678)

    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "min_max",
                "name": "test",
                "type": "mean",
                "entity_ids": ["sensor.test_1", "sensor.test_2"],
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3

    assert hass.states.get("sensor.test")

    yaml_path = get_fixture_path("configuration.yaml", "min_max")

    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3

    assert hass.states.get("sensor.test") is None
    assert hass.states.get("sensor.second_test")


async def test_sensor_incorrect_state(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the min sensor."""
    config = {
        "sensor": {
            "platform": "min_max",
            "name": "test_failure",
            "type": "min",
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES_ERROR, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_failure")

    assert state.state == "15.3"
    assert "Unable to store state. Only numerical states are supported" in caplog.text


async def test_sum_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the sum sensor."""
    config = {
        "sensor": {
            "platform": "min_max",
            "name": "test_sum",
            "type": "sum",
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id_sum_sensor",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")

    assert str(float(SUM_VALUE)) == state.state
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    entity = entity_registry.async_get("sensor.test_sum")
    assert entity.unique_id == "very_unique_id_sum_sensor"


async def test_sum_sensor_no_state(hass: HomeAssistant) -> None:
    """Test the sum sensor with no state ."""
    config = {
        "sensor": {
            "platform": "min_max",
            "name": "test_sum",
            "type": "sum",
            "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id_sum_sensor",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES_ERROR, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")

    assert state.state == STATE_UNKNOWN
