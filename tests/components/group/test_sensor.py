"""The tests for the Group Sensor platform."""
from __future__ import annotations

from math import prod
import statistics
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant import config as hass_config
from homeassistant.components.group import DOMAIN as GROUP_DOMAIN
from homeassistant.components.group.sensor import (
    ATTR_LAST_ENTITY_ID,
    ATTR_MAX_ENTITY_ID,
    ATTR_MIN_ENTITY_ID,
    DEFAULT_NAME,
)
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
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
MEAN = statistics.mean(VALUES)
MEDIAN = statistics.median(VALUES)
RANGE = max(VALUES) - min(VALUES)
SUM_VALUE = sum(VALUES)
PRODUCT_VALUE = prod(VALUES)


@pytest.mark.parametrize(
    ("sensor_type", "result", "attributes"),
    [
        ("min", MIN_VALUE, {ATTR_MIN_ENTITY_ID: "sensor.test_3"}),
        ("max", MAX_VALUE, {ATTR_MAX_ENTITY_ID: "sensor.test_2"}),
        ("mean", MEAN, {}),
        ("median", MEDIAN, {}),
        ("last", VALUES[2], {ATTR_LAST_ENTITY_ID: "sensor.test_3"}),
        ("range", RANGE, {}),
        ("sum", SUM_VALUE, {}),
        ("product", PRODUCT_VALUE, {}),
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    sensor_type: str,
    result: str,
    attributes: dict[str, Any],
) -> None:
    """Test the sensors."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": DEFAULT_NAME,
            "type": sensor_type,
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id",
        }
    }

    entity_ids = config["sensor"]["entities"]

    for entity_id, value in dict(zip(entity_ids, VALUES)).items():
        hass.states.async_set(
            entity_id,
            value,
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.VOLUME,
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: "L",
            },
        )
        await hass.async_block_till_done()

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.sensor_group_{sensor_type}")

    assert float(state.state) == pytest.approx(float(result))
    assert state.attributes.get(ATTR_ENTITY_ID) == entity_ids
    for key, value in attributes.items():
        assert state.attributes.get(key) == value
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLUME
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "L"

    entity = entity_registry.async_get(f"sensor.sensor_group_{sensor_type}")
    assert entity.unique_id == "very_unique_id"


async def test_sensors_attributes_defined(hass: HomeAssistant) -> None:
    """Test the sensors."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": DEFAULT_NAME,
            "type": "sum",
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id",
            "device_class": SensorDeviceClass.WATER,
            "state_class": SensorStateClass.TOTAL_INCREASING,
            "unit_of_measurement": "m³",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entities"]

    for entity_id, value in dict(zip(entity_ids, VALUES)).items():
        hass.states.async_set(
            entity_id,
            value,
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.VOLUME,
                ATTR_STATE_CLASS: SensorStateClass.MEASUREMENT,
                ATTR_UNIT_OF_MEASUREMENT: "L",
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.sensor_group_sum")

    assert state.state == str(float(SUM_VALUE))
    assert state.attributes.get(ATTR_ENTITY_ID) == entity_ids
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.WATER
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "m³"


async def test_not_enough_sensor_value(hass: HomeAssistant) -> None:
    """Test that there is nothing done if not enough values available."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": "test_max",
            "type": "max",
            "ignore_non_numeric": True,
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "state_class": SensorStateClass.MEASUREMENT,
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entities"]

    hass.states.async_set(entity_ids[0], STATE_UNKNOWN)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_max")
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get("min_entity_id") is None
    assert state.attributes.get("max_entity_id") is None

    hass.states.async_set(entity_ids[1], VALUES[1])
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_max")
    assert state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]
    assert entity_ids[1] == state.attributes.get("max_entity_id")

    hass.states.async_set(entity_ids[2], STATE_UNKNOWN)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_max")
    assert state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]
    assert entity_ids[1] == state.attributes.get("max_entity_id")

    hass.states.async_set(entity_ids[1], STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_max")
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get("min_entity_id") is None
    assert state.attributes.get("max_entity_id") is None


async def test_reload(hass: HomeAssistant) -> None:
    """Verify we can reload sensors."""
    hass.states.async_set("sensor.test_1", 12345)
    hass.states.async_set("sensor.test_2", 45678)

    await async_setup_component(
        hass,
        "sensor",
        {
            SENSOR_DOMAIN: {
                "platform": GROUP_DOMAIN,
                "name": "test_sensor",
                "type": "mean",
                "entities": ["sensor.test_1", "sensor.test_2"],
                "state_class": SensorStateClass.MEASUREMENT,
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3

    assert hass.states.get("sensor.test_sensor")

    yaml_path = get_fixture_path("sensor_configuration.yaml", "group")

    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            GROUP_DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3

    assert hass.states.get("sensor.test_sensor") is None
    assert hass.states.get("sensor.second_test")


async def test_sensor_incorrect_state(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the min sensor."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": "test_failure",
            "type": "min",
            "ignore_non_numeric": True,
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id",
            "state_class": SensorStateClass.MEASUREMENT,
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entities"]

    for entity_id, value in dict(zip(entity_ids, VALUES_ERROR)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_failure")

    assert state.state == "15.3"
    assert (
        "Unable to use state. Only numerical states are supported, entity sensor.test_2 with value string excluded from calculation"
        in caplog.text
    )

    for entity_id, value in dict(zip(entity_ids, VALUES)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_failure")
    assert state.state == "15.3"


async def test_sensor_require_all_states(hass: HomeAssistant) -> None:
    """Test the sum sensor with missing state require all."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": "test_sum",
            "type": "sum",
            "ignore_non_numeric": False,
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id_sum_sensor",
            "state_class": SensorStateClass.MEASUREMENT,
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entities"]

    for entity_id, value in dict(zip(entity_ids, VALUES_ERROR)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")

    assert state.state == STATE_UNKNOWN


async def test_sensor_calculated_properties(hass: HomeAssistant) -> None:
    """Test the sensor calculating device_class, state_class and unit of measurement."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": "test_sum",
            "type": "sum",
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id_sum_sensor",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entities"]

    hass.states.async_set(
        entity_ids[0],
        VALUES[0],
        {
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.MEASUREMENT,
            "unit_of_measurement": "kWh",
        },
    )
    hass.states.async_set(
        entity_ids[1],
        VALUES[1],
        {
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.MEASUREMENT,
            "unit_of_measurement": "kWh",
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")
    assert state.state == str(float(sum([VALUES[0], VALUES[1]])))
    assert state.attributes.get("device_class") == "energy"
    assert state.attributes.get("state_class") == "measurement"
    assert state.attributes.get("unit_of_measurement") == "kWh"

    hass.states.async_set(
        entity_ids[2],
        VALUES[2],
        {
            "device_class": SensorDeviceClass.BATTERY,
            "state_class": SensorStateClass.TOTAL,
            "unit_of_measurement": None,
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")
    assert state.state == str(sum(VALUES))
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("state_class") is None
    assert state.attributes.get("unit_of_measurement") is None


async def test_last_sensor(hass: HomeAssistant) -> None:
    """Test the last sensor."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": "test_last",
            "type": "last",
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id_last_sensor",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entities"]

    for entity_id, value in dict(zip(entity_ids, VALUES)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test_last")
        assert str(float(value)) == state.state
        assert entity_id == state.attributes.get("last_entity_id")
