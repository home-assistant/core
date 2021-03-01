"""The tests for the Command line Binary sensor platform."""
from homeassistant import setup
from homeassistant.components.binary_sensor import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.typing import Any, Dict, HomeAssistantType


async def setup_test_entity(
    hass: HomeAssistantType, config_dict: Dict[str, Any]
) -> None:
    """Set up a test command line binary_sensor entity."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"platform": "command_line", "name": "Test", **config_dict}},
    )
    await hass.async_block_till_done()


async def test_setup(hass: HomeAssistantType) -> None:
    """Test sensor setup."""
    await setup_test_entity(
        hass,
        {
            "command": "echo 1",
            "payload_on": "1",
            "payload_off": "0",
        },
    )

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state
    assert entity_state.state == STATE_ON
    assert entity_state.name == "Test"


async def test_template(hass: HomeAssistantType) -> None:
    """Test setting the state with a template."""

    await setup_test_entity(
        hass,
        {
            "command": "echo 10",
            "payload_on": "1.0",
            "payload_off": "0",
            "value_template": "{{ value | multiply(0.1) }}",
        },
    )

    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state.state == STATE_ON


async def test_sensor_off(hass: HomeAssistantType) -> None:
    """Test setting the state with a template."""
    await setup_test_entity(
        hass,
        {
            "command": "echo 0",
            "payload_on": "1",
            "payload_off": "0",
        },
    )
    entity_state = hass.states.get("binary_sensor.test")
    assert entity_state.state == STATE_OFF
