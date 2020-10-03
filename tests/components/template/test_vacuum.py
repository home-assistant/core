"""The tests for the Template vacuum platform."""
import logging

import pytest

from homeassistant import setup
from homeassistant.components.vacuum import (
    ATTR_BATTERY_LEVEL,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN

from tests.common import assert_setup_component, async_mock_service
from tests.components.vacuum import common

_LOGGER = logging.getLogger(__name__)

_TEST_VACUUM = "vacuum.test_vacuum"
_STATE_INPUT_SELECT = "input_select.state"
_SPOT_CLEANING_INPUT_BOOLEAN = "input_boolean.spot_cleaning"
_LOCATING_INPUT_BOOLEAN = "input_boolean.locating"
_FAN_SPEED_INPUT_SELECT = "input_select.fan_speed"
_BATTERY_LEVEL_INPUT_NUMBER = "input_number.battery_level"


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


# Configuration tests #
async def test_missing_optional_config(hass, calls):
    """Test: missing optional template is ok."""
    with assert_setup_component(1, "vacuum"):
        assert await setup.async_setup_component(
            hass,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_vacuum": {"start": {"service": "script.vacuum_start"}}
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN, None)


async def test_missing_start_config(hass, calls):
    """Test: missing 'start' will fail."""
    with assert_setup_component(0, "vacuum"):
        assert await setup.async_setup_component(
            hass,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {"test_vacuum": {"value_template": "{{ 'on' }}"}},
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_invalid_config(hass, calls):
    """Test: invalid config structure will fail."""
    with assert_setup_component(0, "vacuum"):
        assert await setup.async_setup_component(
            hass,
            "vacuum",
            {
                "platform": "template",
                "vacuums": {
                    "test_vacuum": {"start": {"service": "script.vacuum_start"}}
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
    """Test templates with values from other entities."""
    with assert_setup_component(1, "vacuum"):
        assert await setup.async_setup_component(
            hass,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_vacuum": {
                            "value_template": "{{ states('input_select.state') }}",
                            "battery_level_template": "{{ states('input_number.battery_level') }}",
                            "start": {"service": "script.vacuum_start"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN, None)

    hass.states.async_set(_STATE_INPUT_SELECT, STATE_CLEANING)
    hass.states.async_set(_BATTERY_LEVEL_INPUT_NUMBER, 100)
    await hass.async_block_till_done()

    _verify(hass, STATE_CLEANING, 100)


async def test_templates_with_valid_values(hass, calls):
    """Test templates with valid values."""
    with assert_setup_component(1, "vacuum"):
        assert await setup.async_setup_component(
            hass,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_vacuum": {
                            "value_template": "{{ 'cleaning' }}",
                            "battery_level_template": "{{ 100 }}",
                            "start": {"service": "script.vacuum_start"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_CLEANING, 100)


async def test_templates_invalid_values(hass, calls):
    """Test templates with invalid values."""
    with assert_setup_component(1, "vacuum"):
        assert await setup.async_setup_component(
            hass,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_vacuum": {
                            "value_template": "{{ 'abc' }}",
                            "battery_level_template": "{{ 101 }}",
                            "start": {"service": "script.vacuum_start"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN, None)


async def test_invalid_templates(hass, calls):
    """Test invalid templates."""
    with assert_setup_component(1, "vacuum"):
        assert await setup.async_setup_component(
            hass,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_vacuum": {
                            "value_template": "{{ this_function_does_not_exist() }}",
                            "battery_level_template": "{{ this_function_does_not_exist() }}",
                            "fan_speed_template": "{{ this_function_does_not_exist() }}",
                            "start": {"service": "script.vacuum_start"},
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN, None)


async def test_available_template_with_entities(hass, calls):
    """Test availability templates with values from other entities."""

    assert await setup.async_setup_component(
        hass,
        "vacuum",
        {
            "vacuum": {
                "platform": "template",
                "vacuums": {
                    "test_template_vacuum": {
                        "availability_template": "{{ is_state('availability_state.state', 'on') }}",
                        "start": {"service": "script.vacuum_start"},
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    # When template returns true..
    hass.states.async_set("availability_state.state", STATE_ON)
    await hass.async_block_till_done()

    # Device State should not be unavailable
    assert hass.states.get("vacuum.test_template_vacuum").state != STATE_UNAVAILABLE

    # When Availability template returns false
    hass.states.async_set("availability_state.state", STATE_OFF)
    await hass.async_block_till_done()

    # device state should be unavailable
    assert hass.states.get("vacuum.test_template_vacuum").state == STATE_UNAVAILABLE


async def test_invalid_availability_template_keeps_component_available(hass, caplog):
    """Test that an invalid availability keeps the device available."""
    assert await setup.async_setup_component(
        hass,
        "vacuum",
        {
            "vacuum": {
                "platform": "template",
                "vacuums": {
                    "test_template_vacuum": {
                        "availability_template": "{{ x - 12 }}",
                        "start": {"service": "script.vacuum_start"},
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("vacuum.test_template_vacuum") != STATE_UNAVAILABLE
    assert ("UndefinedError: 'x' is undefined") in caplog.text


async def test_attribute_templates(hass, calls):
    """Test attribute_templates template."""
    assert await setup.async_setup_component(
        hass,
        "vacuum",
        {
            "vacuum": {
                "platform": "template",
                "vacuums": {
                    "test_template_vacuum": {
                        "value_template": "{{ 'cleaning' }}",
                        "start": {"service": "script.vacuum_start"},
                        "attribute_templates": {
                            "test_attribute": "It {{ states.sensor.test_state.state }}."
                        },
                    }
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("vacuum.test_template_vacuum")
    assert state.attributes["test_attribute"] == "It ."

    hass.states.async_set("sensor.test_state", "Works")
    await hass.async_block_till_done()
    await hass.helpers.entity_component.async_update_entity(
        "vacuum.test_template_vacuum"
    )
    state = hass.states.get("vacuum.test_template_vacuum")
    assert state.attributes["test_attribute"] == "It Works."


async def test_invalid_attribute_template(hass, caplog):
    """Test that errors are logged if rendering template fails."""
    assert await setup.async_setup_component(
        hass,
        "vacuum",
        {
            "vacuum": {
                "platform": "template",
                "vacuums": {
                    "invalid_template": {
                        "value_template": "{{ states('input_select.state') }}",
                        "start": {"service": "script.vacuum_start"},
                        "attribute_templates": {
                            "test_attribute": "{{ this_function_does_not_exist() }}"
                        },
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 1

    await hass.async_start()
    await hass.async_block_till_done()

    assert "test_attribute" in caplog.text
    assert "TemplateError" in caplog.text


# End of template tests #


# Function tests #
async def test_state_services(hass, calls):
    """Test state services."""
    await _register_components(hass)

    # Start vacuum
    await common.async_start(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_STATE_INPUT_SELECT).state == STATE_CLEANING
    _verify(hass, STATE_CLEANING, None)

    # Pause vacuum
    await common.async_pause(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_STATE_INPUT_SELECT).state == STATE_PAUSED
    _verify(hass, STATE_PAUSED, None)

    # Stop vacuum
    await common.async_stop(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_STATE_INPUT_SELECT).state == STATE_IDLE
    _verify(hass, STATE_IDLE, None)

    # Return vacuum to base
    await common.async_return_to_base(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_STATE_INPUT_SELECT).state == STATE_RETURNING
    _verify(hass, STATE_RETURNING, None)


async def test_unused_services(hass, calls):
    """Test calling unused services should not crash."""
    await _register_basic_vacuum(hass)

    # Pause vacuum
    await common.async_pause(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # Stop vacuum
    await common.async_stop(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # Return vacuum to base
    await common.async_return_to_base(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # Spot cleaning
    await common.async_clean_spot(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # Locate vacuum
    await common.async_locate(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # Set fan's speed
    await common.async_set_fan_speed(hass, "medium", _TEST_VACUUM)
    await hass.async_block_till_done()

    _verify(hass, STATE_UNKNOWN, None)


async def test_clean_spot_service(hass, calls):
    """Test clean spot service."""
    await _register_components(hass)

    # Clean spot
    await common.async_clean_spot(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_SPOT_CLEANING_INPUT_BOOLEAN).state == STATE_ON


async def test_locate_service(hass, calls):
    """Test locate service."""
    await _register_components(hass)

    # Locate vacuum
    await common.async_locate(hass, _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_LOCATING_INPUT_BOOLEAN).state == STATE_ON


async def test_set_fan_speed(hass, calls):
    """Test set valid fan speed."""
    await _register_components(hass)

    # Set vacuum's fan speed to high
    await common.async_set_fan_speed(hass, "high", _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_FAN_SPEED_INPUT_SELECT).state == "high"

    # Set fan's speed to medium
    await common.async_set_fan_speed(hass, "medium", _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_FAN_SPEED_INPUT_SELECT).state == "medium"


async def test_set_invalid_fan_speed(hass, calls):
    """Test set invalid fan speed when fan has valid speed."""
    await _register_components(hass)

    # Set vacuum's fan speed to high
    await common.async_set_fan_speed(hass, "high", _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_FAN_SPEED_INPUT_SELECT).state == "high"

    # Set vacuum's fan speed to 'invalid'
    await common.async_set_fan_speed(hass, "invalid", _TEST_VACUUM)
    await hass.async_block_till_done()

    # verify fan speed is unchanged
    assert hass.states.get(_FAN_SPEED_INPUT_SELECT).state == "high"


def _verify(hass, expected_state, expected_battery_level):
    """Verify vacuum's state and speed."""
    state = hass.states.get(_TEST_VACUUM)
    attributes = state.attributes
    assert state.state == expected_state
    assert attributes.get(ATTR_BATTERY_LEVEL) == expected_battery_level


async def _register_basic_vacuum(hass):
    """Register basic vacuum with only required options for testing."""
    with assert_setup_component(1, "input_select"):
        assert await setup.async_setup_component(
            hass,
            "input_select",
            {"input_select": {"state": {"name": "State", "options": [STATE_CLEANING]}}},
        )

    with assert_setup_component(1, "vacuum"):
        assert await setup.async_setup_component(
            hass,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {
                        "test_vacuum": {
                            "start": {
                                "service": "input_select.select_option",
                                "data": {
                                    "entity_id": _STATE_INPUT_SELECT,
                                    "option": STATE_CLEANING,
                                },
                            }
                        }
                    },
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def _register_components(hass):
    """Register basic components for testing."""
    with assert_setup_component(2, "input_boolean"):
        assert await setup.async_setup_component(
            hass,
            "input_boolean",
            {"input_boolean": {"spot_cleaning": None, "locating": None}},
        )

    with assert_setup_component(2, "input_select"):
        assert await setup.async_setup_component(
            hass,
            "input_select",
            {
                "input_select": {
                    "state": {
                        "name": "State",
                        "options": [
                            STATE_CLEANING,
                            STATE_DOCKED,
                            STATE_IDLE,
                            STATE_PAUSED,
                            STATE_RETURNING,
                        ],
                    },
                    "fan_speed": {
                        "name": "Fan speed",
                        "options": ["", "low", "medium", "high"],
                    },
                }
            },
        )

    with assert_setup_component(1, "vacuum"):
        test_vacuum_config = {
            "value_template": "{{ states('input_select.state') }}",
            "fan_speed_template": "{{ states('input_select.fan_speed') }}",
            "start": {
                "service": "input_select.select_option",
                "data": {"entity_id": _STATE_INPUT_SELECT, "option": STATE_CLEANING},
            },
            "pause": {
                "service": "input_select.select_option",
                "data": {"entity_id": _STATE_INPUT_SELECT, "option": STATE_PAUSED},
            },
            "stop": {
                "service": "input_select.select_option",
                "data": {"entity_id": _STATE_INPUT_SELECT, "option": STATE_IDLE},
            },
            "return_to_base": {
                "service": "input_select.select_option",
                "data": {"entity_id": _STATE_INPUT_SELECT, "option": STATE_RETURNING},
            },
            "clean_spot": {
                "service": "input_boolean.turn_on",
                "entity_id": _SPOT_CLEANING_INPUT_BOOLEAN,
            },
            "locate": {
                "service": "input_boolean.turn_on",
                "entity_id": _LOCATING_INPUT_BOOLEAN,
            },
            "set_fan_speed": {
                "service": "input_select.select_option",
                "data_template": {
                    "entity_id": _FAN_SPEED_INPUT_SELECT,
                    "option": "{{ fan_speed }}",
                },
            },
            "fan_speeds": ["low", "medium", "high"],
            "attribute_templates": {
                "test_attribute": "It {{ states.sensor.test_state.state }}."
            },
        }

        assert await setup.async_setup_component(
            hass,
            "vacuum",
            {
                "vacuum": {
                    "platform": "template",
                    "vacuums": {"test_vacuum": test_vacuum_config},
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def test_unique_id(hass):
    """Test unique_id option only creates one vacuum per id."""
    await setup.async_setup_component(
        hass,
        "vacuum",
        {
            "vacuum": {
                "platform": "template",
                "vacuums": {
                    "test_template_vacuum_01": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ true }}",
                        "start": {"service": "script.vacuum_start"},
                    },
                    "test_template_vacuum_02": {
                        "unique_id": "not-so-unique-anymore",
                        "value_template": "{{ false }}",
                        "start": {"service": "script.vacuum_start"},
                    },
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
