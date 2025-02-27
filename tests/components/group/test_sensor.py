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
    PERCENTAGE,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
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
STDEV = statistics.stdev(VALUES)
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
        ("stdev", STDEV, {}),
        ("sum", SUM_VALUE, {}),
        ("product", PRODUCT_VALUE, {}),
    ],
)
async def test_sensors2(
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

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(
            entity_id,
            value,
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.VOLUME,
                ATTR_STATE_CLASS: SensorStateClass.TOTAL,
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
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL
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

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
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

    # Liter to M3 = 1:0.001
    assert state.state == str(float(SUM_VALUE * 0.001))
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


async def test_sensor_incorrect_state_with_ignore_non_numeric(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that non numeric values are ignored in a group."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": "test_ignore_non_numeric",
            "type": "max",
            "ignore_non_numeric": True,
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id",
            "state_class": SensorStateClass.MEASUREMENT,
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entities"]

    # Check that the final sensor value ignores the non numeric input
    for entity_id, value in dict(zip(entity_ids, VALUES_ERROR, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_ignore_non_numeric")
    assert state.state == "17.0"
    assert (
        "Unable to use state. Only numerical states are supported," not in caplog.text
    )

    # Check that the final sensor value with all numeric inputs
    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_ignore_non_numeric")
    assert state.state == "20.0"


async def test_sensor_incorrect_state_with_not_ignore_non_numeric(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that non numeric values cause a group to be unknown."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": "test_failure",
            "type": "max",
            "ignore_non_numeric": False,
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id",
            "state_class": SensorStateClass.MEASUREMENT,
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_ids = config["sensor"]["entities"]

    # Check that the final sensor value is unavailable if a non numeric input exists
    for entity_id, value in dict(zip(entity_ids, VALUES_ERROR, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_failure")
    assert state.state == "unknown"
    assert "Unable to use state. Only numerical states are supported" in caplog.text

    # Check that the final sensor value is correct with all numeric inputs
    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_failure")
    assert state.state == "20.0"


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

    for entity_id, value in dict(zip(entity_ids, VALUES_ERROR, strict=False)).items():
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

    entity_ids = config["sensor"]["entities"]

    hass.states.async_set(
        entity_ids[0],
        VALUES[0],
        {
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL,
            "unit_of_measurement": "kWh",
        },
    )
    hass.states.async_set(
        entity_ids[1],
        VALUES[1],
        {
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL,
            "unit_of_measurement": "kWh",
        },
    )
    hass.states.async_set(
        entity_ids[2],
        VALUES[2],
        {
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL,
            "unit_of_measurement": "Wh",
        },
    )
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")
    assert state.state == str(float(sum([VALUES[0], VALUES[1], VALUES[2] / 1000])))
    assert state.attributes.get("device_class") == "energy"
    assert state.attributes.get("state_class") == "total"
    assert state.attributes.get("unit_of_measurement") == "kWh"

    # Test that a change of source entity's unit of measurement
    # is converted correctly by the group sensor
    hass.states.async_set(
        entity_ids[2],
        VALUES[2],
        {
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL,
            "unit_of_measurement": "kWh",
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")
    assert state.state == str(float(sum(VALUES)))


async def test_sensor_with_uoms_but_no_device_class(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the sensor works with same uom when there is no device class."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": "test_sum",
            "type": "sum",
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id_last_sensor",
        }
    }

    entity_ids = config["sensor"]["entities"]

    hass.states.async_set(
        entity_ids[0],
        VALUES[0],
        {
            "device_class": SensorDeviceClass.POWER,
            "state_class": SensorStateClass.MEASUREMENT,
            "unit_of_measurement": "W",
        },
    )
    hass.states.async_set(
        entity_ids[1],
        VALUES[1],
        {
            "device_class": SensorDeviceClass.POWER,
            "state_class": SensorStateClass.MEASUREMENT,
            "unit_of_measurement": "W",
        },
    )
    hass.states.async_set(
        entity_ids[2],
        VALUES[2],
        {
            "unit_of_measurement": "W",
        },
    )

    await hass.async_block_till_done()

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("state_class") is None
    assert state.attributes.get("unit_of_measurement") == "W"
    assert state.state == str(float(sum(VALUES)))

    assert not issue_registry.issues

    hass.states.async_set(
        entity_ids[0],
        VALUES[0],
        {
            "device_class": SensorDeviceClass.POWER,
            "state_class": SensorStateClass.MEASUREMENT,
            "unit_of_measurement": "kW",
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.test_sum")
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("state_class") is None
    assert state.attributes.get("unit_of_measurement") is None
    assert state.state == STATE_UNKNOWN

    assert (
        "Unable to use state. Only entities with correct unit of measurement is supported"
        in caplog.text
    )

    hass.states.async_set(
        entity_ids[0],
        VALUES[0],
        {
            "device_class": SensorDeviceClass.POWER,
            "state_class": SensorStateClass.MEASUREMENT,
            "unit_of_measurement": "W",
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.test_sum")
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("state_class") is None
    assert state.attributes.get("unit_of_measurement") == "W"
    assert state.state == str(float(sum(VALUES)))


async def test_sensor_calculated_properties_not_same(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the sensor calculating device_class, state_class and unit of measurement not same."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": "test_sum",
            "type": "sum",
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id_sum_sensor",
        }
    }

    entity_ids = config["sensor"]["entities"]

    hass.states.async_set(
        entity_ids[0],
        VALUES[0],
        {
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL,
            "unit_of_measurement": "kWh",
        },
    )
    hass.states.async_set(
        entity_ids[1],
        VALUES[1],
        {
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL,
            "unit_of_measurement": "kWh",
        },
    )
    hass.states.async_set(
        entity_ids[2],
        VALUES[2],
        {
            "device_class": SensorDeviceClass.CURRENT,
            "state_class": SensorStateClass.MEASUREMENT,
            "unit_of_measurement": "A",
        },
    )
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")
    assert state.state == str(float(sum(VALUES)))
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("state_class") is None
    assert state.attributes.get("unit_of_measurement") is None

    assert issue_registry.async_get_issue(
        GROUP_DOMAIN, "sensor.test_sum_uoms_not_matching_no_device_class"
    )
    assert issue_registry.async_get_issue(
        GROUP_DOMAIN, "sensor.test_sum_device_classes_not_matching"
    )
    assert issue_registry.async_get_issue(
        GROUP_DOMAIN, "sensor.test_sum_state_classes_not_matching"
    )


async def test_sensor_calculated_result_fails_on_uom(hass: HomeAssistant) -> None:
    """Test the sensor calculating fails as UoM not part of device class."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": "test_sum",
            "type": "sum",
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id_sum_sensor",
        }
    }

    entity_ids = config["sensor"]["entities"]

    hass.states.async_set(
        entity_ids[0],
        VALUES[0],
        {
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL,
            "unit_of_measurement": "kWh",
        },
    )
    hass.states.async_set(
        entity_ids[1],
        VALUES[1],
        {
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL,
            "unit_of_measurement": "kWh",
        },
    )
    hass.states.async_set(
        entity_ids[2],
        VALUES[2],
        {
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL,
            "unit_of_measurement": "kWh",
        },
    )
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")
    assert state.state == str(float(sum(VALUES)))
    assert state.attributes.get("device_class") == "energy"
    assert state.attributes.get("state_class") == "total"
    assert state.attributes.get("unit_of_measurement") == "kWh"

    hass.states.async_set(
        entity_ids[2],
        12,
        {
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL,
        },
        True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get("device_class") == "energy"
    assert state.attributes.get("state_class") == "total"
    assert state.attributes.get("unit_of_measurement") is None


async def test_sensor_calculated_properties_not_convertible_device_class(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the sensor calculating device_class, state_class and unit of measurement when device class not convertible."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": "test_sum",
            "type": "sum",
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id_sum_sensor",
        }
    }

    entity_ids = config["sensor"]["entities"]

    hass.states.async_set(
        entity_ids[0],
        VALUES[0],
        {
            "device_class": SensorDeviceClass.HUMIDITY,
            "state_class": SensorStateClass.MEASUREMENT,
            "unit_of_measurement": PERCENTAGE,
        },
    )
    hass.states.async_set(
        entity_ids[1],
        VALUES[1],
        {
            "device_class": SensorDeviceClass.HUMIDITY,
            "state_class": SensorStateClass.MEASUREMENT,
            "unit_of_measurement": PERCENTAGE,
        },
    )
    hass.states.async_set(
        entity_ids[2],
        VALUES[2],
        {
            "device_class": SensorDeviceClass.HUMIDITY,
            "state_class": SensorStateClass.MEASUREMENT,
            "unit_of_measurement": PERCENTAGE,
        },
    )
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")
    assert state.state == str(sum(VALUES))
    assert state.attributes.get("device_class") == "humidity"
    assert state.attributes.get("state_class") == "measurement"
    assert state.attributes.get("unit_of_measurement") == "%"

    assert (
        "Unable to use state. Only entities with correct unit of measurement is"
        " supported"
    ) not in caplog.text

    hass.states.async_set(
        entity_ids[2],
        VALUES[2],
        {
            "device_class": SensorDeviceClass.HUMIDITY,
            "state_class": SensorStateClass.MEASUREMENT,
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("device_class") == "humidity"
    assert state.attributes.get("state_class") == "measurement"
    assert state.attributes.get("unit_of_measurement") is None

    assert (
        "Unable to use state. Only entities with correct unit of measurement is"
        " supported, entity sensor.test_3, value 15.3 with"
        " device class humidity and unit of measurement None excluded from calculation"
        " in sensor.test_sum"
    ) in caplog.text


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

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test_last")
        assert str(float(value)) == state.state
        assert entity_id == state.attributes.get("last_entity_id")


async def test_sensors_attributes_added_when_entity_info_available(
    hass: HomeAssistant,
) -> None:
    """Test the sensor calculate attributes once all entities attributes are available."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": DEFAULT_NAME,
            "type": "sum",
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id",
        }
    }

    entity_ids = config["sensor"]["entities"]

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.sensor_group_sum")

    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get(ATTR_ENTITY_ID) is None
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(
            entity_id,
            value,
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.VOLUME,
                ATTR_STATE_CLASS: SensorStateClass.TOTAL,
                ATTR_UNIT_OF_MEASUREMENT: "L",
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.sensor_group_sum")

    assert float(state.state) == pytest.approx(float(SUM_VALUE))
    assert state.attributes.get(ATTR_ENTITY_ID) == entity_ids
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLUME
    assert state.attributes.get(ATTR_ICON) is None
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "L"


async def test_sensor_state_class_no_uom_not_available(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when input sensors drops unit of measurement."""

    # If we have a valid unit of measurement from all input sensors
    # the group sensor will go unknown in the case any input sensor
    # drops the unit of measurement and log a warning.

    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": "test_sum",
            "type": "sum",
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id_sum_sensor",
        }
    }

    entity_ids = config["sensor"]["entities"]

    input_attributes = {
        "state_class": SensorStateClass.MEASUREMENT,
        "unit_of_measurement": PERCENTAGE,
    }

    hass.states.async_set(entity_ids[0], VALUES[0], input_attributes)
    hass.states.async_set(entity_ids[1], VALUES[1], input_attributes)
    hass.states.async_set(entity_ids[2], VALUES[2], input_attributes)
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")
    assert state.state == str(sum(VALUES))
    assert state.attributes.get("state_class") == "measurement"
    assert state.attributes.get("unit_of_measurement") == "%"

    assert (
        "Unable to use state. Only entities with correct unit of measurement is"
        " supported"
    ) not in caplog.text

    # sensor.test_3 drops the unit of measurement
    hass.states.async_set(
        entity_ids[2],
        VALUES[2],
        {
            "state_class": SensorStateClass.MEASUREMENT,
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("state_class") == "measurement"
    assert state.attributes.get("unit_of_measurement") is None

    assert (
        "Unable to use state. Only entities with correct unit of measurement is"
        " supported, entity sensor.test_3, value 15.3 with"
        " device class None and unit of measurement None excluded from calculation"
        " in sensor.test_sum"
    ) in caplog.text


async def test_sensor_different_attributes_ignore_non_numeric(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the sensor handles calculating attributes when using ignore_non_numeric."""
    config = {
        SENSOR_DOMAIN: {
            "platform": GROUP_DOMAIN,
            "name": "test_sum",
            "type": "sum",
            "ignore_non_numeric": True,
            "entities": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
            "unique_id": "very_unique_id_sum_sensor",
        }
    }

    entity_ids = config["sensor"]["entities"]

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sum")
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get("state_class") is None
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("unit_of_measurement") is None

    test_cases = [
        {
            "entity": entity_ids[0],
            "value": VALUES[0],
            "attributes": {
                "state_class": SensorStateClass.MEASUREMENT,
                "unit_of_measurement": PERCENTAGE,
            },
            "expected_state": str(float(VALUES[0])),
            "expected_state_class": SensorStateClass.MEASUREMENT,
            "expected_device_class": None,
            "expected_unit_of_measurement": PERCENTAGE,
        },
        {
            "entity": entity_ids[1],
            "value": VALUES[1],
            "attributes": {
                "state_class": SensorStateClass.MEASUREMENT,
                "device_class": SensorDeviceClass.HUMIDITY,
                "unit_of_measurement": PERCENTAGE,
            },
            "expected_state": str(float(sum([VALUES[0], VALUES[1]]))),
            "expected_state_class": SensorStateClass.MEASUREMENT,
            "expected_device_class": None,
            "expected_unit_of_measurement": PERCENTAGE,
        },
        {
            "entity": entity_ids[2],
            "value": VALUES[2],
            "attributes": {
                "state_class": SensorStateClass.MEASUREMENT,
                "device_class": SensorDeviceClass.TEMPERATURE,
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
            },
            "expected_state": str(float(sum(VALUES))),
            "expected_state_class": SensorStateClass.MEASUREMENT,
            "expected_device_class": None,
            "expected_unit_of_measurement": None,
        },
        {
            "entity": entity_ids[2],
            "value": VALUES[2],
            "attributes": {
                "state_class": SensorStateClass.MEASUREMENT,
                "device_class": SensorDeviceClass.HUMIDITY,
                "unit_of_measurement": PERCENTAGE,
            },
            "expected_state": str(float(sum(VALUES))),
            "expected_state_class": SensorStateClass.MEASUREMENT,
            # One sensor does not have a device class
            "expected_device_class": None,
            "expected_unit_of_measurement": PERCENTAGE,
        },
        {
            "entity": entity_ids[0],
            "value": VALUES[0],
            "attributes": {
                "state_class": SensorStateClass.MEASUREMENT,
                "device_class": SensorDeviceClass.HUMIDITY,
                "unit_of_measurement": PERCENTAGE,
            },
            "expected_state": str(float(sum(VALUES))),
            "expected_state_class": SensorStateClass.MEASUREMENT,
            # First sensor now has a device class
            "expected_device_class": SensorDeviceClass.HUMIDITY,
            "expected_unit_of_measurement": PERCENTAGE,
        },
        {
            "entity": entity_ids[0],
            "value": VALUES[0],
            "attributes": {
                "state_class": SensorStateClass.MEASUREMENT,
            },
            "expected_state": str(float(sum(VALUES))),
            "expected_state_class": SensorStateClass.MEASUREMENT,
            "expected_device_class": None,
            "expected_unit_of_measurement": None,
        },
    ]

    for test_case in test_cases:
        hass.states.async_set(
            test_case["entity"],
            test_case["value"],
            test_case["attributes"],
        )
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test_sum")
        assert state.state == test_case["expected_state"]
        assert state.attributes.get("state_class") == test_case["expected_state_class"]
        assert (
            state.attributes.get("device_class") == test_case["expected_device_class"]
        )
        assert (
            state.attributes.get("unit_of_measurement")
            == test_case["expected_unit_of_measurement"]
        )
