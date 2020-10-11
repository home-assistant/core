"""The tests for the integration sensor platform."""
from homeassistant.components.compensation.sensor import ATTR_COEFFICIENTS
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.setup import async_setup_component


async def test_linear_state(hass):
    """Test compensation sensor state."""
    config = {
        "sensor": {
            "platform": "compensation",
            "name": "compensation",
            "entity_id": "sensor.uncompensated",
            "data_points": [
                "1.0 -> 2.0",
                "2.0 -> 3.0",
            ],
            "precision": 2,
            ATTR_UNIT_OF_MEASUREMENT: "a",
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["entity_id"]
    hass.states.async_set(entity_id, 4, {})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.compensation")
    assert state is not None

    assert round(float(state.state), config["sensor"]["precision"]) == 5.0

    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == config["sensor"][ATTR_UNIT_OF_MEASUREMENT]
    )

    coefs = [round(v, 1) for v in state.attributes.get(ATTR_COEFFICIENTS)]
    assert coefs == [1.0, 1.0]


async def test_linear_state_from_attribute(hass):
    """Test compensation sensor state that pulls from attribute."""
    config = {
        "sensor": {
            "platform": "compensation",
            "name": "compensation",
            "entity_id": "sensor.uncompensated",
            "attribute": "value",
            "data_points": [
                "1.0 -> 2.0",
                "2.0 -> 3.0",
            ],
            "precision": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["entity_id"]
    hass.states.async_set(entity_id, 3, {"value": 4})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.compensation")
    assert state is not None

    assert round(float(state.state), config["sensor"]["precision"]) == 5.0

    coefs = [round(v, 1) for v in state.attributes.get(ATTR_COEFFICIENTS)]
    assert coefs == [1.0, 1.0]


async def test_quadratic_state(hass):
    """Test 3 degree polynominial compensation sensor."""
    config = {
        "sensor": {
            "platform": "compensation",
            "name": "compensation",
            "entity_id": "sensor.temperature",
            "data_points": [
                "50 -> 3.3",
                "50 -> 2.8",
                "50 -> 2.9",
                "70 -> 2.3",
                "70 -> 2.6",
                "70 -> 2.1",
                "80 -> 2.5",
                "80 -> 2.9",
                "80 -> 2.4",
                "90 -> 3.0",
                "90 -> 3.1",
                "90 -> 2.8",
                "100 -> 3.3",
                "100 -> 3.5",
                "100 -> 3.0",
            ],
            "degree": 2,
            "precision": 3,
        }
    }
    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["entity_id"]
    hass.states.async_set(entity_id, 43.2, {})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.compensation")

    assert state is not None

    assert round(float(state.state), config["sensor"]["precision"]) == 3.327
