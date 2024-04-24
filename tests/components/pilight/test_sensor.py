"""The tests for the Pilight sensor platform."""

import logging

import pytest

from homeassistant.components import pilight, sensor
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, mock_component


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, "pilight")


def fire_pilight_message(hass, protocol, data):
    """Fire the fake Pilight message."""
    message = {pilight.CONF_PROTOCOL: protocol}
    message.update(data)

    hass.bus.async_fire(pilight.EVENT, message)


async def test_sensor_value_from_code(hass: HomeAssistant) -> None:
    """Test the setting of value via pilight."""
    with assert_setup_component(1):
        assert await async_setup_component(
            hass,
            sensor.DOMAIN,
            {
                sensor.DOMAIN: {
                    "platform": "pilight",
                    "name": "test",
                    "variable": "test",
                    "payload": {"protocol": "test-protocol"},
                    "unit_of_measurement": "fav unit",
                }
            },
        )
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test")
        assert state.state == "unknown"

        unit_of_measurement = state.attributes.get("unit_of_measurement")
        assert unit_of_measurement == "fav unit"

        # Set value from data with correct payload
        fire_pilight_message(hass, protocol="test-protocol", data={"test": 42})
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test")
        assert state.state == "42"


async def test_disregard_wrong_payload(hass: HomeAssistant) -> None:
    """Test omitting setting of value with wrong payload."""
    with assert_setup_component(1):
        assert await async_setup_component(
            hass,
            sensor.DOMAIN,
            {
                sensor.DOMAIN: {
                    "platform": "pilight",
                    "name": "test_2",
                    "variable": "test",
                    "payload": {"uuid": "1-2-3-4", "protocol": "test-protocol_2"},
                }
            },
        )
        await hass.async_block_till_done()

        # Try set value from data with incorrect payload
        fire_pilight_message(
            hass, protocol="test-protocol_2", data={"test": "data", "uuid": "0-0-0-0"}
        )
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test_2")
        assert state.state == "unknown"

        # Try set value from data with partially matched payload
        fire_pilight_message(
            hass, protocol="wrong-protocol", data={"test": "data", "uuid": "1-2-3-4"}
        )
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test_2")
        assert state.state == "unknown"

        # Try set value from data with fully matched payload
        fire_pilight_message(
            hass,
            protocol="test-protocol_2",
            data={"test": "data", "uuid": "1-2-3-4", "other_payload": 3.141},
        )
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test_2")
        assert state.state == "data"


async def test_variable_missing(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Check if error message when variable missing."""
    caplog.set_level(logging.ERROR)
    with assert_setup_component(1):
        assert await async_setup_component(
            hass,
            sensor.DOMAIN,
            {
                sensor.DOMAIN: {
                    "platform": "pilight",
                    "name": "test_3",
                    "variable": "test",
                    "payload": {"protocol": "test-protocol"},
                }
            },
        )
        await hass.async_block_till_done()

        # Create code without sensor variable
        fire_pilight_message(
            hass,
            protocol="test-protocol",
            data={"uuid": "1-2-3-4", "other_variable": 3.141},
        )
        await hass.async_block_till_done()

        logs = caplog.text

        assert "No variable test in received code" in logs
