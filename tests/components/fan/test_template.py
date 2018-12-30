"""The tests for the Template fan platform."""
import logging
import pytest

from homeassistant import setup
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.components.fan import (
    ATTR_SPEED, ATTR_OSCILLATING, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH,
    ATTR_DIRECTION, DIRECTION_FORWARD, DIRECTION_REVERSE)

from tests.common import (
    async_mock_service, assert_setup_component)
from tests.components.fan import common

_LOGGER = logging.getLogger(__name__)


_TEST_FAN = 'fan.test_fan'
# Represent for fan's state
_STATE_INPUT_BOOLEAN = 'input_boolean.state'
# Represent for fan's speed
_SPEED_INPUT_SELECT = 'input_select.speed'
# Represent for fan's oscillating
_OSC_INPUT = 'input_select.osc'
# Represent for fan's direction
_DIRECTION_INPUT_SELECT = 'input_select.direction'


@pytest.fixture
def calls(hass):
    """Track calls to a mock serivce."""
    return async_mock_service(hass, 'test', 'automation')


# Configuration tests #
async def test_missing_optional_config(hass, calls):
    """Test: missing optional template is ok."""
    with assert_setup_component(1, 'fan'):
        assert await setup.async_setup_component(hass, 'fan', {
            'fan': {
                'platform': 'template',
                'fans': {
                    'test_fan': {
                        'value_template': "{{ 'on' }}",

                        'turn_on': {
                            'service': 'script.fan_on'
                        },
                        'turn_off': {
                            'service': 'script.fan_off'
                        }
                    }
                }
            }
        })

    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_ON, None, None, None)


async def test_missing_value_template_config(hass, calls):
    """Test: missing 'value_template' will fail."""
    with assert_setup_component(0, 'fan'):
        assert await setup.async_setup_component(hass, 'fan', {
            'fan': {
                'platform': 'template',
                'fans': {
                    'test_fan': {
                        'turn_on': {
                            'service': 'script.fan_on'
                        },
                        'turn_off': {
                            'service': 'script.fan_off'
                        }
                    }
                }
            }
        })

    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_missing_turn_on_config(hass, calls):
    """Test: missing 'turn_on' will fail."""
    with assert_setup_component(0, 'fan'):
        assert await setup.async_setup_component(hass, 'fan', {
            'fan': {
                'platform': 'template',
                'fans': {
                    'test_fan': {
                        'value_template': "{{ 'on' }}",
                        'turn_off': {
                            'service': 'script.fan_off'
                        }
                    }
                }
            }
        })

    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_missing_turn_off_config(hass, calls):
    """Test: missing 'turn_off' will fail."""
    with assert_setup_component(0, 'fan'):
        assert await setup.async_setup_component(hass, 'fan', {
            'fan': {
                'platform': 'template',
                'fans': {
                    'test_fan': {
                        'value_template': "{{ 'on' }}",
                        'turn_on': {
                            'service': 'script.fan_on'
                        }
                    }
                }
            }
        })

    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_invalid_config(hass, calls):
    """Test: missing 'turn_off' will fail."""
    with assert_setup_component(0, 'fan'):
        assert await setup.async_setup_component(hass, 'fan', {
            'platform': 'template',
            'fans': {
                'test_fan': {
                    'value_template': "{{ 'on' }}",
                    'turn_on': {
                        'service': 'script.fan_on'
                    }
                }
            }
        })

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

    with assert_setup_component(1, 'fan'):
        assert await setup.async_setup_component(hass, 'fan', {
            'fan': {
                'platform': 'template',
                'fans': {
                    'test_fan': {
                        'value_template': value_template,
                        'speed_template':
                            "{{ states('input_select.speed') }}",
                        'oscillating_template':
                            "{{ states('input_select.osc') }}",
                        'direction_template':
                            "{{ states('input_select.direction') }}",
                        'turn_on': {
                            'service': 'script.fan_on'
                        },
                        'turn_off': {
                            'service': 'script.fan_off'
                        }
                    }
                }
            }
        })

    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_OFF, None, None, None)

    hass.states.async_set(_STATE_INPUT_BOOLEAN, True)
    hass.states.async_set(_SPEED_INPUT_SELECT, SPEED_MEDIUM)
    hass.states.async_set(_OSC_INPUT, 'True')
    hass.states.async_set(_DIRECTION_INPUT_SELECT, DIRECTION_FORWARD)
    await hass.async_block_till_done()

    _verify(hass, STATE_ON, SPEED_MEDIUM, True, DIRECTION_FORWARD)


async def test_templates_with_valid_values(hass, calls):
    """Test templates with valid values."""
    with assert_setup_component(1, 'fan'):
        assert await setup.async_setup_component(hass, 'fan', {
            'fan': {
                'platform': 'template',
                'fans': {
                    'test_fan': {
                        'value_template':
                            "{{ 'on' }}",
                        'speed_template':
                            "{{ 'medium' }}",
                        'oscillating_template':
                            "{{ 1 == 1 }}",
                        'direction_template':
                            "{{ 'forward' }}",

                        'turn_on': {
                            'service': 'script.fan_on'
                        },
                        'turn_off': {
                            'service': 'script.fan_off'
                        }
                    }
                }
            }
        })

    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_ON, SPEED_MEDIUM, True, DIRECTION_FORWARD)


async def test_templates_invalid_values(hass, calls):
    """Test templates with invalid values."""
    with assert_setup_component(1, 'fan'):
        assert await setup.async_setup_component(hass, 'fan', {
            'fan': {
                'platform': 'template',
                'fans': {
                    'test_fan': {
                        'value_template':
                            "{{ 'abc' }}",
                        'speed_template':
                            "{{ '0' }}",
                        'oscillating_template':
                            "{{ 'xyz' }}",
                        'direction_template':
                            "{{ 'right' }}",

                        'turn_on': {
                            'service': 'script.fan_on'
                        },
                        'turn_off': {
                            'service': 'script.fan_off'
                        }
                    }
                }
            }
        })

    await hass.async_start()
    await hass.async_block_till_done()

    _verify(hass, STATE_OFF, None, None, None)

# End of template tests #


# Function tests #
async def test_on_off(hass, calls):
    """Test turn on and turn off."""
    await _register_components(hass)

    # Turn on fan
    common.async_turn_on(hass, _TEST_FAN)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_STATE_INPUT_BOOLEAN).state == STATE_ON
    _verify(hass, STATE_ON, None, None, None)

    # Turn off fan
    common.async_turn_off(hass, _TEST_FAN)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_STATE_INPUT_BOOLEAN).state == STATE_OFF
    _verify(hass, STATE_OFF, None, None, None)


async def test_on_with_speed(hass, calls):
    """Test turn on with speed."""
    await _register_components(hass)

    # Turn on fan with high speed
    common.async_turn_on(hass, _TEST_FAN, SPEED_HIGH)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_STATE_INPUT_BOOLEAN).state == STATE_ON
    assert hass.states.get(_SPEED_INPUT_SELECT).state == SPEED_HIGH
    _verify(hass, STATE_ON, SPEED_HIGH, None, None)


async def test_set_speed(hass, calls):
    """Test set valid speed."""
    await _register_components(hass)

    # Turn on fan
    common.async_turn_on(hass, _TEST_FAN)
    await hass.async_block_till_done()

    # Set fan's speed to high
    common.async_set_speed(hass, _TEST_FAN, SPEED_HIGH)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_SPEED_INPUT_SELECT).state == SPEED_HIGH
    _verify(hass, STATE_ON, SPEED_HIGH, None, None)

    # Set fan's speed to medium
    common.async_set_speed(hass, _TEST_FAN, SPEED_MEDIUM)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_SPEED_INPUT_SELECT).state == SPEED_MEDIUM
    _verify(hass, STATE_ON, SPEED_MEDIUM, None, None)


async def test_set_invalid_speed_from_initial_stage(hass, calls):
    """Test set invalid speed when fan is in initial state."""
    await _register_components(hass)

    # Turn on fan
    common.async_turn_on(hass, _TEST_FAN)
    await hass.async_block_till_done()

    # Set fan's speed to 'invalid'
    common.async_set_speed(hass, _TEST_FAN, 'invalid')
    await hass.async_block_till_done()

    # verify speed is unchanged
    assert hass.states.get(_SPEED_INPUT_SELECT).state == ''
    _verify(hass, STATE_ON, None, None, None)


async def test_set_invalid_speed(hass, calls):
    """Test set invalid speed when fan has valid speed."""
    await _register_components(hass)

    # Turn on fan
    common.async_turn_on(hass, _TEST_FAN)
    await hass.async_block_till_done()

    # Set fan's speed to high
    common.async_set_speed(hass, _TEST_FAN, SPEED_HIGH)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_SPEED_INPUT_SELECT).state == SPEED_HIGH
    _verify(hass, STATE_ON, SPEED_HIGH, None, None)

    # Set fan's speed to 'invalid'
    common.async_set_speed(hass, _TEST_FAN, 'invalid')
    await hass.async_block_till_done()

    # verify speed is unchanged
    assert hass.states.get(_SPEED_INPUT_SELECT).state == SPEED_HIGH
    _verify(hass, STATE_ON, SPEED_HIGH, None, None)


async def test_custom_speed_list(hass, calls):
    """Test set custom speed list."""
    await _register_components(hass, ['1', '2', '3'])

    # Turn on fan
    common.async_turn_on(hass, _TEST_FAN)
    await hass.async_block_till_done()

    # Set fan's speed to '1'
    common.async_set_speed(hass, _TEST_FAN, '1')
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_SPEED_INPUT_SELECT).state == '1'
    _verify(hass, STATE_ON, '1', None, None)

    # Set fan's speed to 'medium' which is invalid
    common.async_set_speed(hass, _TEST_FAN, SPEED_MEDIUM)
    await hass.async_block_till_done()

    # verify that speed is unchanged
    assert hass.states.get(_SPEED_INPUT_SELECT).state == '1'
    _verify(hass, STATE_ON, '1', None, None)


async def test_set_osc(hass, calls):
    """Test set oscillating."""
    await _register_components(hass)

    # Turn on fan
    common.async_turn_on(hass, _TEST_FAN)
    await hass.async_block_till_done()

    # Set fan's osc to True
    common.async_oscillate(hass, _TEST_FAN, True)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_OSC_INPUT).state == 'True'
    _verify(hass, STATE_ON, None, True, None)

    # Set fan's osc to False
    common.async_oscillate(hass, _TEST_FAN, False)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_OSC_INPUT).state == 'False'
    _verify(hass, STATE_ON, None, False, None)


async def test_set_invalid_osc_from_initial_state(hass, calls):
    """Test set invalid oscillating when fan is in initial state."""
    await _register_components(hass)

    # Turn on fan
    common.async_turn_on(hass, _TEST_FAN)
    await hass.async_block_till_done()

    # Set fan's osc to 'invalid'
    common.async_oscillate(hass, _TEST_FAN, 'invalid')
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_OSC_INPUT).state == ''
    _verify(hass, STATE_ON, None, None, None)


async def test_set_invalid_osc(hass, calls):
    """Test set invalid oscillating when fan has valid osc."""
    await _register_components(hass)

    # Turn on fan
    common.async_turn_on(hass, _TEST_FAN)
    await hass.async_block_till_done()

    # Set fan's osc to True
    common.async_oscillate(hass, _TEST_FAN, True)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_OSC_INPUT).state == 'True'
    _verify(hass, STATE_ON, None, True, None)

    # Set fan's osc to False
    common.async_oscillate(hass, _TEST_FAN, None)
    await hass.async_block_till_done()

    # verify osc is unchanged
    assert hass.states.get(_OSC_INPUT).state == 'True'
    _verify(hass, STATE_ON, None, True, None)


async def test_set_direction(hass, calls):
    """Test set valid direction."""
    await _register_components(hass)

    # Turn on fan
    common.async_turn_on(hass, _TEST_FAN)
    await hass.async_block_till_done()

    # Set fan's direction to forward
    common.async_set_direction(hass, _TEST_FAN, DIRECTION_FORWARD)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_DIRECTION_INPUT_SELECT).state \
        == DIRECTION_FORWARD
    _verify(hass, STATE_ON, None, None, DIRECTION_FORWARD)

    # Set fan's direction to reverse
    common.async_set_direction(hass, _TEST_FAN, DIRECTION_REVERSE)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_DIRECTION_INPUT_SELECT).state \
        == DIRECTION_REVERSE
    _verify(hass, STATE_ON, None, None, DIRECTION_REVERSE)


async def test_set_invalid_direction_from_initial_stage(hass, calls):
    """Test set invalid direction when fan is in initial state."""
    await _register_components(hass)

    # Turn on fan
    common.async_turn_on(hass, _TEST_FAN)
    await hass.async_block_till_done()

    # Set fan's direction to 'invalid'
    common.async_set_direction(hass, _TEST_FAN, 'invalid')
    await hass.async_block_till_done()

    # verify direction is unchanged
    assert hass.states.get(_DIRECTION_INPUT_SELECT).state == ''
    _verify(hass, STATE_ON, None, None, None)


async def test_set_invalid_direction(hass, calls):
    """Test set invalid direction when fan has valid direction."""
    await _register_components(hass)

    # Turn on fan
    common.async_turn_on(hass, _TEST_FAN)
    await hass.async_block_till_done()

    # Set fan's direction to forward
    common.async_set_direction(hass, _TEST_FAN, DIRECTION_FORWARD)
    await hass.async_block_till_done()

    # verify
    assert hass.states.get(_DIRECTION_INPUT_SELECT).state == \
        DIRECTION_FORWARD
    _verify(hass, STATE_ON, None, None, DIRECTION_FORWARD)

    # Set fan's direction to 'invalid'
    common.async_set_direction(hass, _TEST_FAN, 'invalid')
    await hass.async_block_till_done()

    # verify direction is unchanged
    assert hass.states.get(_DIRECTION_INPUT_SELECT).state == \
        DIRECTION_FORWARD
    _verify(hass, STATE_ON, None, None, DIRECTION_FORWARD)


def _verify(hass, expected_state, expected_speed, expected_oscillating,
            expected_direction):
    """Verify fan's state, speed and osc."""
    state = hass.states.get(_TEST_FAN)
    attributes = state.attributes
    assert state.state == expected_state
    assert attributes.get(ATTR_SPEED, None) == expected_speed
    assert attributes.get(ATTR_OSCILLATING, None) == expected_oscillating
    assert attributes.get(ATTR_DIRECTION, None) == expected_direction


async def _register_components(hass, speed_list=None):
    """Register basic components for testing."""
    with assert_setup_component(1, 'input_boolean'):
        assert await setup.async_setup_component(
            hass,
            'input_boolean',
            {'input_boolean': {'state': None}}
        )

    with assert_setup_component(3, 'input_select'):
        assert await setup.async_setup_component(hass, 'input_select', {
            'input_select': {
                'speed': {
                    'name': 'Speed',
                    'options': ['', SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH,
                                '1', '2', '3']
                },

                'osc': {
                    'name': 'oscillating',
                    'options': ['', 'True', 'False']
                },

                'direction': {
                    'name': 'Direction',
                    'options': ['', DIRECTION_FORWARD, DIRECTION_REVERSE]
                },
            }
        })

    with assert_setup_component(1, 'fan'):
        value_template = """
        {% if is_state('input_boolean.state', 'on') %}
            {{ 'on' }}
        {% else %}
            {{ 'off' }}
        {% endif %}
        """

        test_fan_config = {
            'value_template': value_template,
            'speed_template':
                "{{ states('input_select.speed') }}",
            'oscillating_template':
                "{{ states('input_select.osc') }}",
            'direction_template':
                "{{ states('input_select.direction') }}",

            'turn_on': {
                'service': 'input_boolean.turn_on',
                'entity_id': _STATE_INPUT_BOOLEAN
            },
            'turn_off': {
                'service': 'input_boolean.turn_off',
                'entity_id': _STATE_INPUT_BOOLEAN
            },
            'set_speed': {
                'service': 'input_select.select_option',

                'data_template': {
                    'entity_id': _SPEED_INPUT_SELECT,
                    'option': '{{ speed }}'
                }
            },
            'set_oscillating': {
                'service': 'input_select.select_option',

                'data_template': {
                    'entity_id': _OSC_INPUT,
                    'option': '{{ oscillating }}'
                }
            },
            'set_direction': {
                'service': 'input_select.select_option',

                'data_template': {
                    'entity_id': _DIRECTION_INPUT_SELECT,
                    'option': '{{ direction }}'
                }
            }
        }

        if speed_list:
            test_fan_config['speeds'] = speed_list

        assert await setup.async_setup_component(hass, 'fan', {
            'fan': {
                'platform': 'template',
                'fans': {
                    'test_fan': test_fan_config
                }
            }
        })

    await hass.async_start()
    await hass.async_block_till_done()
