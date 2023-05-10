"""The tests for the integration sensor platform."""
import pytest

from homeassistant.components.compensation.const import CONF_PRECISION, DOMAIN
from homeassistant.components.compensation.sensor import ATTR_COEFFICIENTS
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_HOMEASSISTANT_START,
    EVENT_STATE_CHANGED,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_linear_state(hass: HomeAssistant) -> None:
    """Test compensation sensor state."""
    config = {
        "compensation": {
            "test": {
                "source": "sensor.uncompensated",
                "data_points": [
                    [1.0, 2.0],
                    [2.0, 3.0],
                ],
                "precision": 2,
                "unit_of_measurement": "a",
            }
        }
    }
    expected_entity_id = "sensor.compensation_sensor_uncompensated"

    assert await async_setup_component(hass, DOMAIN, config)
    assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    entity_id = config[DOMAIN]["test"]["source"]
    hass.states.async_set(entity_id, 4, {})
    await hass.async_block_till_done()

    state = hass.states.get(expected_entity_id)
    assert state is not None

    assert round(float(state.state), config[DOMAIN]["test"][CONF_PRECISION]) == 5.0

    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "a"

    coefs = [round(v, 1) for v in state.attributes.get(ATTR_COEFFICIENTS)]
    assert coefs == [1.0, 1.0]

    hass.states.async_set(entity_id, "foo", {})
    await hass.async_block_till_done()

    state = hass.states.get(expected_entity_id)
    assert state is not None

    assert state.state == STATE_UNKNOWN


async def test_linear_state_from_attribute(hass: HomeAssistant) -> None:
    """Test compensation sensor state that pulls from attribute."""
    config = {
        "compensation": {
            "test": {
                "source": "sensor.uncompensated",
                "attribute": "value",
                "data_points": [
                    [1.0, 2.0],
                    [2.0, 3.0],
                ],
                "precision": 2,
            }
        }
    }
    expected_entity_id = "sensor.compensation_sensor_uncompensated_value"

    assert await async_setup_component(hass, DOMAIN, config)
    assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)

    entity_id = config[DOMAIN]["test"]["source"]
    hass.states.async_set(entity_id, 3, {"value": 4})
    await hass.async_block_till_done()

    state = hass.states.get(expected_entity_id)
    assert state is not None

    assert round(float(state.state), config[DOMAIN]["test"][CONF_PRECISION]) == 5.0

    coefs = [round(v, 1) for v in state.attributes.get(ATTR_COEFFICIENTS)]
    assert coefs == [1.0, 1.0]

    hass.states.async_set(entity_id, 3, {"value": "bar"})
    await hass.async_block_till_done()

    state = hass.states.get(expected_entity_id)
    assert state is not None

    assert state.state == STATE_UNKNOWN


async def test_quadratic_state(hass: HomeAssistant) -> None:
    """Test 3 degree polynominial compensation sensor."""
    config = {
        "compensation": {
            "test": {
                "source": "sensor.temperature",
                "data_points": [
                    [50, 3.3],
                    [50, 2.8],
                    [50, 2.9],
                    [70, 2.3],
                    [70, 2.6],
                    [70, 2.1],
                    [80, 2.5],
                    [80, 2.9],
                    [80, 2.4],
                    [90, 3.0],
                    [90, 3.1],
                    [90, 2.8],
                    [100, 3.3],
                    [100, 3.5],
                    [100, 3.0],
                ],
                "degree": 2,
                "precision": 3,
            }
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    entity_id = config[DOMAIN]["test"]["source"]
    hass.states.async_set(entity_id, 43.2, {})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.compensation_sensor_temperature")

    assert state is not None

    assert round(float(state.state), config[DOMAIN]["test"][CONF_PRECISION]) == 3.327


async def test_numpy_errors(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Tests bad polyfits."""
    config = {
        "compensation": {
            "test": {
                "source": "sensor.uncompensated",
                "data_points": [
                    [0.0, 1.0],
                    [0.0, 1.0],
                ],
            },
        }
    }
    await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert "invalid value encountered in divide" in caplog.text


async def test_datapoints_greater_than_degree(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Tests 3 bad data points."""
    config = {
        "compensation": {
            "test": {
                "source": "sensor.uncompensated",
                "data_points": [
                    [1.0, 2.0],
                    [2.0, 3.0],
                ],
                "degree": 2,
            },
        }
    }
    await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert "data_points must have at least 3 data_points" in caplog.text


async def test_new_state_is_none(hass: HomeAssistant) -> None:
    """Tests catch for empty new states."""
    config = {
        "compensation": {
            "test": {
                "source": "sensor.uncompensated",
                "data_points": [
                    [1.0, 2.0],
                    [2.0, 3.0],
                ],
                "precision": 2,
                "unit_of_measurement": "a",
            }
        }
    }
    expected_entity_id = "sensor.compensation_sensor_uncompensated"

    await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    last_changed = hass.states.get(expected_entity_id).last_changed

    hass.bus.async_fire(
        EVENT_STATE_CHANGED, event_data={"entity_id": "sensor.uncompensated"}
    )

    assert last_changed == hass.states.get(expected_entity_id).last_changed
