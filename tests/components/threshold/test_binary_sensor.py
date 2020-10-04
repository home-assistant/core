"""The test for the threshold sensor platform."""

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN, TEMP_CELSIUS
from homeassistant.setup import async_setup_component


async def test_sensor_upper(hass):
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

    hass.states.async_set(
        "sensor.test_monitored", 16, {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS}
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "sensor.test_monitored" == state.attributes.get("entity_id")
    assert 16 == state.attributes.get("sensor_value")
    assert "above" == state.attributes.get("position")
    assert float(config["binary_sensor"]["upper"]) == state.attributes.get("upper")
    assert 0.0 == state.attributes.get("hysteresis")
    assert "upper" == state.attributes.get("type")

    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 14)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 15)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert state.state == "off"


async def test_sensor_lower(hass):
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

    hass.states.async_set("sensor.test_monitored", 16)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "above" == state.attributes.get("position")
    assert float(config["binary_sensor"]["lower"]) == state.attributes.get("lower")
    assert 0.0 == state.attributes.get("hysteresis")
    assert "lower" == state.attributes.get("type")

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 14)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert state.state == "on"


async def test_sensor_hysteresis(hass):
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

    hass.states.async_set("sensor.test_monitored", 20)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "above" == state.attributes.get("position")
    assert float(config["binary_sensor"]["upper"]) == state.attributes.get("upper")
    assert 2.5 == state.attributes.get("hysteresis")
    assert "upper" == state.attributes.get("type")

    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 13)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 12)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 17)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 18)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert state.state == "on"


async def test_sensor_in_range_no_hysteresis(hass):
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
        "sensor.test_monitored", 16, {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS}
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert state.attributes.get("entity_id") == "sensor.test_monitored"
    assert 16 == state.attributes.get("sensor_value")
    assert "in_range" == state.attributes.get("position")
    assert float(config["binary_sensor"]["lower"]) == state.attributes.get("lower")
    assert float(config["binary_sensor"]["upper"]) == state.attributes.get("upper")
    assert 0.0 == state.attributes.get("hysteresis")
    assert "range" == state.attributes.get("type")

    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 9)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "below" == state.attributes.get("position")
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 21)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "above" == state.attributes.get("position")
    assert state.state == "off"


async def test_sensor_in_range_with_hysteresis(hass):
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

    hass.states.async_set(
        "sensor.test_monitored", 16, {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS}
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "sensor.test_monitored" == state.attributes.get("entity_id")
    assert 16 == state.attributes.get("sensor_value")
    assert "in_range" == state.attributes.get("position")
    assert float(config["binary_sensor"]["lower"]) == state.attributes.get("lower")
    assert float(config["binary_sensor"]["upper"]) == state.attributes.get("upper")
    assert float(config["binary_sensor"]["hysteresis"]) == state.attributes.get(
        "hysteresis"
    )
    assert "range" == state.attributes.get("type")

    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 8)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "in_range" == state.attributes.get("position")
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 7)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "below" == state.attributes.get("position")
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 12)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "below" == state.attributes.get("position")
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 13)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "in_range" == state.attributes.get("position")
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 22)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "in_range" == state.attributes.get("position")
    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", 23)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "above" == state.attributes.get("position")
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 18)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "above" == state.attributes.get("position")
    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 17)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "in_range" == state.attributes.get("position")
    assert state.state == "on"


async def test_sensor_in_range_unknown_state(hass):
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
        "sensor.test_monitored", 16, {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS}
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "sensor.test_monitored" == state.attributes.get("entity_id")
    assert 16 == state.attributes.get("sensor_value")
    assert "in_range" == state.attributes.get("position")
    assert float(config["binary_sensor"]["lower"]) == state.attributes.get("lower")
    assert float(config["binary_sensor"]["upper"]) == state.attributes.get("upper")
    assert 0.0 == state.attributes.get("hysteresis")
    assert "range" == state.attributes.get("type")

    assert state.state == "on"

    hass.states.async_set("sensor.test_monitored", STATE_UNKNOWN)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert "unknown" == state.attributes.get("position")
    assert state.state == "off"


async def test_sensor_lower_zero_threshold(hass):
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

    assert "lower" == state.attributes.get("type")
    assert float(config["binary_sensor"]["lower"]) == state.attributes.get("lower")

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", -3)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert state.state == "on"


async def test_sensor_upper_zero_threshold(hass):
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

    assert "upper" == state.attributes.get("type")
    assert float(config["binary_sensor"]["upper"]) == state.attributes.get("upper")

    assert state.state == "off"

    hass.states.async_set("sensor.test_monitored", 2)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.threshold")

    assert state.state == "on"
