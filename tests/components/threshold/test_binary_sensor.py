"""The test for the threshold sensor platform."""

import pytest

from homeassistant.components.threshold.const import DOMAIN
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_sensor_upper(hass: HomeAssistant) -> None:
    """Test if source is above threshold."""
    config = {
        "binary_sensor": {
            "platform": "threshold",
            "upper": "15",
            "entity_id": "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    # Set the monitored sensor's state to the threshold
    hass.states.async_set("sensor.test_monitored", 15)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "off"

    hass.states.async_set(
        "sensor.test_monitored",
        16,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["entity_id"] == "sensor.test_monitored"
    assert state.attributes["sensor_value"] == 16
    assert state.attributes["position"] == "above"
    assert state.attributes["upper"] == float(config["binary_sensor"]["upper"])
    assert state.attributes["hysteresis"] == 0.0
    assert state.attributes["type"] == "upper"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 14)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 15)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", "cat")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

    hass.states.async_set("sensor.test_monitored", 15)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "off"


async def test_sensor_lower(hass: HomeAssistant) -> None:
    """Test if source is below threshold."""
    config = {
        "binary_sensor": {
            "platform": "threshold",
            "lower": "15",
            "entity_id": "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    # Set the monitored sensor's state to the threshold
    hass.states.async_set("sensor.test_monitored", 15)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 16)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.attributes["lower"] == float(config["binary_sensor"]["lower"])
    assert state.attributes["hysteresis"] == 0.0
    assert state.attributes["type"] == "lower"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 14)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 15)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", "cat")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

    hass.states.async_set("sensor.test_monitored", 15)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.state == "off"


async def test_sensor_upper_hysteresis(hass: HomeAssistant) -> None:
    """Test if source is above threshold using hysteresis."""
    config = {
        "binary_sensor": {
            "platform": "threshold",
            "upper": "15",
            "hysteresis": "2.5",
            "entity_id": "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    # Set the monitored sensor's state to the threshold + hysteresis
    hass.states.async_set("sensor.test_monitored", 17.5)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "off"

    # Set the monitored sensor's state to the threshold - hysteresis
    hass.states.async_set("sensor.test_monitored", 12.5)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 20)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.attributes["upper"] == float(config["binary_sensor"]["upper"])
    assert state.attributes["hysteresis"] == 2.5
    assert state.attributes["type"] == "upper"
    assert state.attributes["position"] == "above"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 13)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 12)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 17)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 18)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", "cat")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

    hass.states.async_set("sensor.test_monitored", 18)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.state == "on"


async def test_sensor_lower_hysteresis(hass: HomeAssistant) -> None:
    """Test if source is below threshold using hysteresis."""
    config = {
        "binary_sensor": {
            "platform": "threshold",
            "lower": "15",
            "hysteresis": "2.5",
            "entity_id": "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    # Set the monitored sensor's state to the threshold + hysteresis
    hass.states.async_set("sensor.test_monitored", 17.5)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.state == "off"

    # Set the monitored sensor's state to the threshold - hysteresis
    hass.states.async_set("sensor.test_monitored", 12.5)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 20)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.attributes["lower"] == float(config["binary_sensor"]["lower"])
    assert state.attributes["hysteresis"] == 2.5
    assert state.attributes["type"] == "lower"
    assert state.attributes["position"] == "above"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 13)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 12)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 17)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 18)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", "cat")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

    hass.states.async_set("sensor.test_monitored", 18)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.state == "off"


async def test_sensor_in_range_no_hysteresis(hass: HomeAssistant) -> None:
    """Test if source is within the range."""
    config = {
        "binary_sensor": {
            "platform": "threshold",
            "lower": "10",
            "upper": "20",
            "entity_id": "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    # Set the monitored sensor's state to the lower threshold
    hass.states.async_set("sensor.test_monitored", 10)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "in_range"
    assert state.state == "on"

    # Set the monitored sensor's state to the upper threshold
    hass.states.async_set("sensor.test_monitored", 20)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "in_range"
    assert state.state == "on"

    hass.states.async_set(
        "sensor.test_monitored",
        16,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["entity_id"] == "sensor.test_monitored"
    assert state.attributes["sensor_value"] == 16
    assert state.attributes["position"] == "in_range"
    assert state.attributes["lower"] == float(config["binary_sensor"]["lower"])
    assert state.attributes["upper"] == float(config["binary_sensor"]["upper"])
    assert state.attributes["hysteresis"] == 0.0
    assert state.attributes["type"] == "range"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 9)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 21)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", "cat")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

    hass.states.async_set("sensor.test_monitored", 21)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.state == "off"


async def test_sensor_in_range_with_hysteresis(hass: HomeAssistant) -> None:
    """Test if source is within the range."""
    config = {
        "binary_sensor": {
            "platform": "threshold",
            "lower": "10",
            "upper": "20",
            "hysteresis": "2",
            "entity_id": "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    # Set the monitored sensor's state to the lower threshold - hysteresis
    hass.states.async_set("sensor.test_monitored", 8)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "in_range"
    assert state.state == "on"

    # Set the monitored sensor's state to the lower threshold + hysteresis
    hass.states.async_set("sensor.test_monitored", 12)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "in_range"
    assert state.state == "on"

    # Set the monitored sensor's state to the upper threshold + hysteresis
    hass.states.async_set("sensor.test_monitored", 22)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "in_range"
    assert state.state == "on"

    # Set the monitored sensor's state to the upper threshold - hysteresis
    hass.states.async_set("sensor.test_monitored", 18)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "in_range"
    assert state.state == "on"

    hass.states.async_set(
        "sensor.test_monitored",
        16,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert state.attributes["entity_id"] == "sensor.test_monitored"
    assert state.attributes["sensor_value"] == 16
    assert state.attributes["position"] == "in_range"
    assert state.attributes["lower"] == float(config["binary_sensor"]["lower"])
    assert state.attributes["upper"] == float(config["binary_sensor"]["upper"])
    assert state.attributes["hysteresis"] == float(
        config["binary_sensor"]["hysteresis"]
    )
    assert state.attributes["type"] == "range"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 8)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "in_range"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 7)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 12)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "below"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 13)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "in_range"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 22)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "in_range"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 23)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 18)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "above"
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 17)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "in_range"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", "cat")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

    hass.states.async_set("sensor.test_monitored", 17)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "in_range"
    assert state.state == "on"


async def test_sensor_in_range_unknown_state(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if source is within the range."""
    config = {
        "binary_sensor": {
            "platform": "threshold",
            "lower": "10",
            "upper": "20",
            "entity_id": "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set(
        "sensor.test_monitored",
        16,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert state.attributes["entity_id"] == "sensor.test_monitored"
    assert state.attributes["sensor_value"] == 16
    assert state.attributes["position"] == "in_range"
    assert state.attributes["lower"] == float(config["binary_sensor"]["lower"])
    assert state.attributes["upper"] == float(config["binary_sensor"]["upper"])
    assert state.attributes["hysteresis"] == 0.0
    assert state.attributes["type"] == "range"
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", STATE_UNKNOWN)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

    hass.states.async_set("sensor.test_monitored", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

    assert "State is not numerical" not in caplog.text


async def test_sensor_lower_zero_threshold(hass: HomeAssistant) -> None:
    """Test if a lower threshold of zero is set."""
    config = {
        "binary_sensor": {
            "platform": "threshold",
            "lower": "0",
            "entity_id": "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", 16)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["type"] == "lower"
    assert state.attributes["lower"] == float(config["binary_sensor"]["lower"])
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", -3)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.state == "on"


async def test_sensor_upper_zero_threshold(hass: HomeAssistant) -> None:
    """Test if an upper threshold of zero is set."""
    config = {
        "binary_sensor": {
            "platform": "threshold",
            "upper": "0",
            "entity_id": "sensor.test_monitored",
        }
    }

    assert await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.test_monitored", -10)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["type"] == "upper"
    assert state.attributes["upper"] == float(config["binary_sensor"]["upper"])
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 2)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.state == "on"


async def test_sensor_no_lower_upper(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if no lower or upper has been provided."""
    config = {
        "binary_sensor": {
            "platform": "threshold",
            "entity_id": "sensor.test_monitored",
        }
    }

    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    assert "Lower or Upper thresholds not provided" in caplog.text


async def test_device_id(hass: HomeAssistant) -> None:
    """Test for source entity device for Threshold."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

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

    utility_meter_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": "sensor.test_source",
            "hysteresis": 0.0,
            "lower": -2.0,
            "name": "Threshold",
            "upper": None,
        },
        title="Threshold",
    )

    utility_meter_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(utility_meter_config_entry.entry_id)
    await hass.async_block_till_done()

    utility_meter_entity = entity_registry.async_get("binary_sensor.threshold")
    assert utility_meter_entity is not None
    assert utility_meter_entity.device_id == source_entity.device_id
