"""The tests for the Template fan platform."""
import logging

import pytest
import voluptuous as vol

from homeassistant import setup
from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_SPEED,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE

from tests.common import assert_setup_component, async_mock_service
from tests.components.fan import common

_LOGGER = logging.getLogger(__name__)


_TEST_FAN = "fan.test_fan"
# Represent for fan's state
_STATE_INPUT_BOOLEAN = "input_boolean.state"
# Represent for fan's state
_STATE_AVAILABILITY_BOOLEAN = "availability_boolean.state"
# Represent for fan's speed
_SPEED_INPUT_SELECT = "input_select.speed"
# Represent for fan's oscillating
_OSC_INPUT = "input_select.osc"
# Represent for fan's direction
_DIRECTION_INPUT_SELECT = "input_select.direction"


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


# Configuration tests #
async def test_missing_optional_config(hass, calls):
    """Test: missing optional template is ok."""
    with assert_setup_component(1, "fan"):
        assert await setup.async_setup_component(
            hass,
            "fan",
            {
                "fan": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "value_template": "{{ 'on' }}",
                            "turn_on": {"service": "script.fan_on"},
                            "turn_off": {"service": "script.fan_off"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_ON, None, None, None)


async def test_missing_value_template_config(hass, calls):
    """Test: missing 'value_template' will fail."""
    with assert_setup_component(0, "fan"):
        assert await setup.async_setup_component(
            hass,
            "fan",
            {
                "fan": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "turn_on": {"service": "script.fan_on"},
                            "turn_off": {"service": "script.fan_off"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_missing_turn_on_config(hass, calls):
    """Test: missing 'turn_on' will fail."""
    with assert_setup_component(0, "fan"):
        assert await setup.async_setup_component(
            hass,
            "fan",
            {
                "fan": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "value_template": "{{ 'on' }}",
                            "turn_off": {"service": "script.fan_off"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_missing_turn_off_config(hass, calls):
    """Test: missing 'turn_off' will fail."""
    with assert_setup_component(0, "fan"):
        assert await setup.async_setup_component(
            hass,
            "fan",
            {
                "fan": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "value_template": "{{ 'on' }}",
                            "turn_on": {"service": "script.fan_on"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_invalid_config(hass, calls):
    """Test: missing 'turn_off' will fail."""
    with assert_setup_component(0, "fan"):
        assert await setup.async_setup_component(
            hass,
            "fan",
            {
                "platform": "template",
                "fans": {
                    "test_fan": {
                        "value_template": "{{ 'on' }}",
                        "turn_on": {"service": "script.fan_on"},
                    }
                },
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


# End of configuration tests #


# Template tests #
async def test_templates_with_entities(hass, calls):
    """Test tempalates with values from other entities."""
    value_template = """
        {% if is_state('input_boolean.state', 'True') %}
            {{ 'on' }}
        {% else %}
            {{ 'off' }}
        {% endif %}
    """

    with assert_setup_component(1, "fan"):
        assert await setup.async_setup_component(
            hass,
            "fan",
            {
                "fan": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "value_template": value_template,
                            "speed_template": "{{ states('input_select.speed') }}",
                            "oscillating_template": "{{ states('input_select.osc') }}",
                            "direction_template": "{{ states('input_select.direction') }}",
                            "turn_on": {"service": "script.fan_on"},
                            "turn_off": {"service": "script.fan_off"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_OFF, None, None, None)

    hass.states.async_set(_STATE_INPUT_BOOLEAN, True)
    hass.states.async_set(_SPEED_INPUT_SELECT, SPEED_MEDIUM)
    hass.states.async_set(_OSC_INPUT, "True")
    hass.states.async_set(_DIRECTION_INPUT_SELECT, DIRECTION_FORWARD)
    await hass.async_block_till_done()

    _verify(hass, STATE_ON, SPEED_MEDIUM, True, DIRECTION_FORWARD)


async def test_template_with_unavailable_entities(hass, calls):
    """Test unavailability with value_template."""

    with assert_setup_component(1, "fan"):
        assert await setup.async_setup_component(
            hass,
            "fan",
            {
                "fan": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "value_template": "{{ 'unavailable' }}",
                            "turn_on": {"service": "script.fan_on"},
                            "turn_off": {"service": "script.fan_off"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()
    assert hass.states.get(_TEST_FAN).state == STATE_OFF


async def test_template_with_unavailable_parameters(hass, calls):
    """Test unavailability of speed, direction and oscillating parameters."""

    with assert_setup_component(1, "fan"):
        assert await setup.async_setup_component(
            hass,
            "fan",
            {
                "fan": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "value_template": "{{ 'on' }}",
                            "speed_template": "{{ 'unavailable' }}",
                            "oscillating_template": "{{ 'unavailable' }}",
                            "direction_template": "{{ 'unavailable' }}",
                            "turn_on": {"service": "script.fan_on"},
                            "turn_off": {"service": "script.fan_off"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_ON, None, None, None)


async def test_availability_template_with_entities(hass, calls):
    """Test availability tempalates with values from other entities."""

    with assert_setup_component(1, "fan"):
        assert await setup.async_setup_component(
            hass,
            "fan",
            {
                "fan": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "availability_template": "{{ is_state('availability_boolean.state', 'on') }}",
                            "value_template": "{{ 'on' }}",
                            "speed_template": "{{ 'medium' }}",
                            "oscillating_template": "{{ 1 == 1 }}",
                            "direction_template": "{{ 'forward' }}",
                            "turn_on": {"service": "script.fan_on"},
                            "turn_off": {"service": "script.fan_off"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # When template returns true..
    hass.states.async_set(_STATE_AVAILABILITY_BOOLEAN, STATE_ON)
    await hass.async_block_till_done()

    # Device State should not be unavailable
    assert hass.states.get(_TEST_FAN).state != STATE_UNAVAILABLE

    # When Availability template returns false
    hass.states.async_set(_STATE_AVAILABILITY_BOOLEAN, STATE_OFF)
    await hass.async_block_till_done()

    # device state should be unavailable
    assert hass.states.get(_TEST_FAN).state == STATE_UNAVAILABLE


async def test_templates_with_valid_values(hass, calls):
    """Test templates with valid values."""
    with assert_setup_component(1, "fan"):
        assert await setup.async_setup_component(
            hass,
            "fan",
            {
                "fan": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "value_template": "{{ 'on' }}",
                            "speed_template": "{{ 'medium' }}",
                            "oscillating_template": "{{ 1 == 1 }}",
                            "direction_template": "{{ 'forward' }}",
                            "turn_on": {"service": "script.fan_on"},
                            "turn_off": {"service": "script.fan_off"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_ON, SPEED_MEDIUM, True, DIRECTION_FORWARD)


async def test_templates_invalid_values(hass, calls):
    """Test templates with invalid values."""
    with assert_setup_component(1, "fan"):
        assert await setup.async_setup_component(
            hass,
            "fan",
            {
                "fan": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "value_template": "{{ 'abc' }}",
                            "speed_template": "{{ '0' }}",
                            "oscillating_template": "{{ 'xyz' }}",
                            "direction_template": "{{ 'right' }}",
                            "turn_on": {"service": "script.fan_on"},
                            "turn_off": {"service": "script.fan_off"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_OFF, None, None, None)


async def test_invalid_availability_template_keeps_component_available(hass, caplog):
    """Test that an invalid availability keeps the device available."""

    with assert_setup_component(1, "fan"):
        assert await setup.async_setup_component(
            hass,
            "fan",
            {
                "fan": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "value_template": "{{ 'on' }}",
                            "availability_template": "{{ x - 12 }}",
                            "speed_template": "{{ states('input_select.speed') }}",
                            "oscillating_template": "{{ states('input_select.osc') }}",
                            "direction_template": "{{ states('input_select.direction') }}",
                            "turn_on": {"service": "script.fan_on"},
                            "turn_off": {"service": "script.fan_off"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("fan.test_fan").state != STATE_UNAVAILABLE

    assert "TemplateError" in caplog.text
    assert "x" in caplog.text


# End of template tests #


# Function tests #
async def test_on_off(hass, calls):
    """Test turn on and turn off."""
    await _register_components(hass)

    # Turn on fan
    await common.async_turn_on(hass, _TEST_FAN)

    # verify
    assert hass.states.get(_STATE_INPUT_BOOLEAN).state == STATE_ON
    _verify(hass, STATE_ON, None, None, None)

    # Turn off fan
    await common.async_turn_off(hass, _TEST_FAN)

    # verify
    assert hass.states.get(_STATE_INPUT_BOOLEAN).state == STATE_OFF
    _verify(hass, STATE_OFF, None, None, None)


async def test_on_with_speed(hass, calls):
    """Test turn on with speed."""
    await _register_components(hass)

    # Turn on fan with high speed
    await common.async_turn_on(hass, _TEST_FAN, SPEED_HIGH)

    # verify
    assert hass.states.get(_STATE_INPUT_BOOLEAN).state == STATE_ON
    assert hass.states.get(_SPEED_INPUT_SELECT).state == SPEED_HIGH
    _verify(hass, STATE_ON, SPEED_HIGH, None, None)


async def test_set_speed(hass, calls):
    """Test set valid speed."""
    await _register_components(hass)

    # Turn on fan
    await common.async_turn_on(hass, _TEST_FAN)

    # Set fan's speed to high
    await common.async_set_speed(hass, _TEST_FAN, SPEED_HIGH)

    # verify
    assert hass.states.get(_SPEED_INPUT_SELECT).state == SPEED_HIGH
    _verify(hass, STATE_ON, SPEED_HIGH, None, None)

    # Set fan's speed to medium
    await common.async_set_speed(hass, _TEST_FAN, SPEED_MEDIUM)

    # verify
    assert hass.states.get(_SPEED_INPUT_SELECT).state == SPEED_MEDIUM
    _verify(hass, STATE_ON, SPEED_MEDIUM, None, None)


async def test_set_invalid_speed_from_initial_stage(hass, calls):
    """Test set invalid speed when fan is in initial state."""
    await _register_components(hass)

    # Turn on fan
    await common.async_turn_on(hass, _TEST_FAN)

    # Set fan's speed to 'invalid'
    await common.async_set_speed(hass, _TEST_FAN, "invalid")

    # verify speed is unchanged
    assert hass.states.get(_SPEED_INPUT_SELECT).state == ""
    _verify(hass, STATE_ON, None, None, None)


async def test_set_invalid_speed(hass, calls):
    """Test set invalid speed when fan has valid speed."""
    await _register_components(hass)

    # Turn on fan
    await common.async_turn_on(hass, _TEST_FAN)

    # Set fan's speed to high
    await common.async_set_speed(hass, _TEST_FAN, SPEED_HIGH)

    # verify
    assert hass.states.get(_SPEED_INPUT_SELECT).state == SPEED_HIGH
    _verify(hass, STATE_ON, SPEED_HIGH, None, None)

    # Set fan's speed to 'invalid'
    await common.async_set_speed(hass, _TEST_FAN, "invalid")

    # verify speed is unchanged
    assert hass.states.get(_SPEED_INPUT_SELECT).state == SPEED_HIGH
    _verify(hass, STATE_ON, SPEED_HIGH, None, None)


async def test_custom_speed_list(hass, calls):
    """Test set custom speed list."""
    await _register_components(hass, ["1", "2", "3"])

    # Turn on fan
    await common.async_turn_on(hass, _TEST_FAN)

    # Set fan's speed to '1'
    await common.async_set_speed(hass, _TEST_FAN, "1")

    # verify
    assert hass.states.get(_SPEED_INPUT_SELECT).state == "1"
    _verify(hass, STATE_ON, "1", None, None)

    # Set fan's speed to 'medium' which is invalid
    await common.async_set_speed(hass, _TEST_FAN, SPEED_MEDIUM)

    # verify that speed is unchanged
    assert hass.states.get(_SPEED_INPUT_SELECT).state == "1"
    _verify(hass, STATE_ON, "1", None, None)


async def test_set_osc(hass, calls):
    """Test set oscillating."""
    await _register_components(hass)

    # Turn on fan
    await common.async_turn_on(hass, _TEST_FAN)

    # Set fan's osc to True
    await common.async_oscillate(hass, _TEST_FAN, True)

    # verify
    assert hass.states.get(_OSC_INPUT).state == "True"
    _verify(hass, STATE_ON, None, True, None)

    # Set fan's osc to False
    await common.async_oscillate(hass, _TEST_FAN, False)

    # verify
    assert hass.states.get(_OSC_INPUT).state == "False"
    _verify(hass, STATE_ON, None, False, None)


async def test_set_invalid_osc_from_initial_state(hass, calls):
    """Test set invalid oscillating when fan is in initial state."""
    await _register_components(hass)

    # Turn on fan
    await common.async_turn_on(hass, _TEST_FAN)

    # Set fan's osc to 'invalid'
    with pytest.raises(vol.Invalid):
        await common.async_oscillate(hass, _TEST_FAN, "invalid")

    # verify
    assert hass.states.get(_OSC_INPUT).state == ""
    _verify(hass, STATE_ON, None, None, None)


async def test_set_invalid_osc(hass, calls):
    """Test set invalid oscillating when fan has valid osc."""
    await _register_components(hass)

    # Turn on fan
    await common.async_turn_on(hass, _TEST_FAN)

    # Set fan's osc to True
    await common.async_oscillate(hass, _TEST_FAN, True)

    # verify
    assert hass.states.get(_OSC_INPUT).state == "True"
    _verify(hass, STATE_ON, None, True, None)

    # Set fan's osc to None
    with pytest.raises(vol.Invalid):
        await common.async_oscillate(hass, _TEST_FAN, None)

    # verify osc is unchanged
    assert hass.states.get(_OSC_INPUT).state == "True"
    _verify(hass, STATE_ON, None, True, None)


async def test_set_direction(hass, calls):
    """Test set valid direction."""
    await _register_components(hass)

    # Turn on fan
    await common.async_turn_on(hass, _TEST_FAN)

    # Set fan's direction to forward
    await common.async_set_direction(hass, _TEST_FAN, DIRECTION_FORWARD)

    # verify
    assert hass.states.get(_DIRECTION_INPUT_SELECT).state == DIRECTION_FORWARD
    _verify(hass, STATE_ON, None, None, DIRECTION_FORWARD)

    # Set fan's direction to reverse
    await common.async_set_direction(hass, _TEST_FAN, DIRECTION_REVERSE)

    # verify
    assert hass.states.get(_DIRECTION_INPUT_SELECT).state == DIRECTION_REVERSE
    _verify(hass, STATE_ON, None, None, DIRECTION_REVERSE)


async def test_set_invalid_direction_from_initial_stage(hass, calls):
    """Test set invalid direction when fan is in initial state."""
    await _register_components(hass)

    # Turn on fan
    await common.async_turn_on(hass, _TEST_FAN)

    # Set fan's direction to 'invalid'
    await common.async_set_direction(hass, _TEST_FAN, "invalid")

    # verify direction is unchanged
    assert hass.states.get(_DIRECTION_INPUT_SELECT).state == ""
    _verify(hass, STATE_ON, None, None, None)


async def test_set_invalid_direction(hass, calls):
    """Test set invalid direction when fan has valid direction."""
    await _register_components(hass)

    # Turn on fan
    await common.async_turn_on(hass, _TEST_FAN)

    # Set fan's direction to forward
    await common.async_set_direction(hass, _TEST_FAN, DIRECTION_FORWARD)

    # verify
    assert hass.states.get(_DIRECTION_INPUT_SELECT).state == DIRECTION_FORWARD
    _verify(hass, STATE_ON, None, None, DIRECTION_FORWARD)

    # Set fan's direction to 'invalid'
    await common.async_set_direction(hass, _TEST_FAN, "invalid")

    # verify direction is unchanged
    assert hass.states.get(_DIRECTION_INPUT_SELECT).state == DIRECTION_FORWARD
    _verify(hass, STATE_ON, None, None, DIRECTION_FORWARD)


def _verify(
    hass, expected_state, expected_speed, expected_oscillating, expected_direction
):
    """Verify fan's state, speed and osc."""
    state = hass.states.get(_TEST_FAN)
    attributes = state.attributes
    assert state.state == expected_state
    assert attributes.get(ATTR_SPEED) == expected_speed
    assert attributes.get(ATTR_OSCILLATING) == expected_oscillating
    assert attributes.get(ATTR_DIRECTION) == expected_direction


async def _register_components(hass, speed_list=None):
    """Register basic components for testing."""
    with assert_setup_component(1, "input_boolean"):
        assert await setup.async_setup_component(
            hass, "input_boolean", {"input_boolean": {"state": None}}
        )

    with assert_setup_component(3, "input_select"):
        assert await setup.async_setup_component(
            hass,
            "input_select",
            {
                "input_select": {
                    "speed": {
                        "name": "Speed",
                        "options": [
                            "",
                            SPEED_LOW,
                            SPEED_MEDIUM,
                            SPEED_HIGH,
                            "1",
                            "2",
                            "3",
                        ],
                    },
                    "osc": {"name": "oscillating", "options": ["", "True", "False"]},
                    "direction": {
                        "name": "Direction",
                        "options": ["", DIRECTION_FORWARD, DIRECTION_REVERSE],
                    },
                }
            },
        )

    with assert_setup_component(1, "fan"):
        value_template = """
        {% if is_state('input_boolean.state', 'on') %}
            {{ 'on' }}
        {% else %}
            {{ 'off' }}
        {% endif %}
        """

        test_fan_config = {
            "value_template": value_template,
            "speed_template": "{{ states('input_select.speed') }}",
            "oscillating_template": "{{ states('input_select.osc') }}",
            "direction_template": "{{ states('input_select.direction') }}",
            "turn_on": {
                "service": "input_boolean.turn_on",
                "entity_id": _STATE_INPUT_BOOLEAN,
            },
            "turn_off": {
                "service": "input_boolean.turn_off",
                "entity_id": _STATE_INPUT_BOOLEAN,
            },
            "set_speed": {
                "service": "input_select.select_option",
                "data_template": {
                    "entity_id": _SPEED_INPUT_SELECT,
                    "option": "{{ speed }}",
                },
            },
            "set_oscillating": {
                "service": "input_select.select_option",
                "data_template": {
                    "entity_id": _OSC_INPUT,
                    "option": "{{ oscillating }}",
                },
            },
            "set_direction": {
                "service": "input_select.select_option",
                "data_template": {
                    "entity_id": _DIRECTION_INPUT_SELECT,
                    "option": "{{ direction }}",
                },
            },
        }

        if speed_list:
            test_fan_config["speeds"] = speed_list

        assert await setup.async_setup_component(
            hass,
            "fan",
            {"fan": {"platform": "template", "fans": {"test_fan": test_fan_config}}},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def test_unique_id(hass):
    """Test unique_id option only creates one fan per id."""
    await setup.async_setup_component(
        hass,
        "fan",
        {
            "fan": {
                "platform": "template",
                "fans": {
                    "test_template_fan_01": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ true }}",
                        "turn_on": {
                            "service": "fan.turn_on",
                            "entity_id": "fan.test_state",
                        },
                        "turn_off": {
                            "service": "fan.turn_off",
                            "entity_id": "fan.test_state",
                        },
                    },
                    "test_template_fan_02": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ false }}",
                        "turn_on": {
                            "service": "fan.turn_on",
                            "entity_id": "fan.test_state",
                        },
                        "turn_off": {
                            "service": "fan.turn_off",
                            "entity_id": "fan.test_state",
                        },
                    },
                },
            },
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
