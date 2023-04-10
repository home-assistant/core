"""The test for the threshold sensor platform."""
import pytest

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


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
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

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
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 15)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
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
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

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
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 15)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
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
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

    # Set the monitored sensor's state to the threshold - hysteresis
    hass.states.async_set("sensor.test_monitored", 12.5)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

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
    assert state.state == "off"

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
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

    # Set the monitored sensor's state to the threshold - hysteresis
    hass.states.async_set("sensor.test_monitored", 12.5)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

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
    assert state.state == "off"

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
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

    # Set the monitored sensor's state to the upper threshold
    hass.states.async_set("sensor.test_monitored", 20)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

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
    assert state.state == "off"

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
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

    # Set the monitored sensor's state to the lower threshold + hysteresis
    hass.states.async_set("sensor.test_monitored", 12)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

    # Set the monitored sensor's state to the upper threshold + hysteresis
    hass.states.async_set("sensor.test_monitored", 22)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

    # Set the monitored sensor's state to the upper threshold - hysteresis
    hass.states.async_set("sensor.test_monitored", 18)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "unknown"

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
    assert state.state == "off"

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
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.threshold")
    assert state.attributes["position"] == "unknown"
    assert state.state == "off"

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
