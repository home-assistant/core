"""The tests for the Template fan platform."""
import pytest
import voluptuous as vol

from homeassistant import setup
from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_SPEED,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE

from tests.common import assert_setup_component
from tests.components.fan import common

_TEST_FAN = "fan.test_fan"
# Represent for fan's state
_STATE_INPUT_BOOLEAN = "input_boolean.state"
# Represent for fan's state
_STATE_AVAILABILITY_BOOLEAN = "availability_boolean.state"
# Represent for fan's speed
_SPEED_INPUT_SELECT = "input_select.speed"
# Represent for fan's preset mode
_PRESET_MODE_INPUT_SELECT = "input_select.preset_mode"
# Represent for fan's speed percentage
_PERCENTAGE_INPUT_NUMBER = "input_number.percentage"
# Represent for fan's oscillating
_OSC_INPUT = "input_select.osc"
# Represent for fan's direction
_DIRECTION_INPUT_SELECT = "input_select.direction"


@pytest.mark.parametrize("count,domain", [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
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
    ],
)
async def test_missing_optional_config(hass, start_ha):
    """Test: missing optional template is ok."""
    _verify(hass, STATE_ON, None, None, None, None, None)


@pytest.mark.parametrize("count,domain", [(0, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "fans": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "turn_on": {"service": "script.fan_on"},
                            "turn_off": {"service": "script.fan_off"},
                        }
                    },
                },
            }
        },
        {
            DOMAIN: {
                "platform": "template",
                "fans": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "value_template": "{{ 'on' }}",
                            "turn_off": {"service": "script.fan_off"},
                        }
                    },
                },
            }
        },
        {
            DOMAIN: {
                "platform": "template",
                "fans": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "value_template": "{{ 'on' }}",
                            "turn_on": {"service": "script.fan_on"},
                        }
                    },
                },
            }
        },
        {
            DOMAIN: {
                "platform": "template",
                "fans": {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "value_template": "{{ 'on' }}",
                            "turn_on": {"service": "script.fan_on"},
                        }
                    },
                },
            }
        },
    ],
)
async def test_wrong_template_config(hass, start_ha):
    """Test: missing 'value_template' will fail."""
    assert hass.states.async_all() == []


@pytest.mark.parametrize("count,domain", [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "fans": {
                    "test_fan": {
                        "value_template": """
        {% if is_state('input_boolean.state', 'True') %}
            {{ 'on' }}
        {% else %}
            {{ 'off' }}
        {% endif %}
    """,
                        "percentage_template": "{{ states('input_number.percentage') }}",
                        "speed_template": "{{ states('input_select.speed') }}",
                        "preset_mode_template": "{{ states('input_select.preset_mode') }}",
                        "oscillating_template": "{{ states('input_select.osc') }}",
                        "direction_template": "{{ states('input_select.direction') }}",
                        "speed_count": "3",
                        "set_percentage": {
                            "service": "script.fans_set_speed",
                            "data_template": {"percentage": "{{ percentage }}"},
                        },
                        "turn_on": {"service": "script.fan_on"},
                        "turn_off": {"service": "script.fan_off"},
                    }
                },
            }
        },
    ],
)
async def test_templates_with_entities(hass, start_ha):
    """Test tempalates with values from other entities."""
    _verify(hass, STATE_OFF, None, 0, None, None, None)

    hass.states.async_set(_STATE_INPUT_BOOLEAN, True)
    hass.states.async_set(_SPEED_INPUT_SELECT, SPEED_MEDIUM)
    hass.states.async_set(_OSC_INPUT, "True")

    for set_state, set_value, speed, value in [
        (_DIRECTION_INPUT_SELECT, DIRECTION_FORWARD, SPEED_MEDIUM, 66),
        (_PERCENTAGE_INPUT_NUMBER, 33, SPEED_LOW, 33),
        (_PERCENTAGE_INPUT_NUMBER, 66, SPEED_MEDIUM, 66),
        (_PERCENTAGE_INPUT_NUMBER, 100, SPEED_HIGH, 100),
        (_PERCENTAGE_INPUT_NUMBER, "dog", None, 0),
    ]:
        hass.states.async_set(set_state, set_value)
        await hass.async_block_till_done()
        _verify(hass, STATE_ON, speed, value, True, DIRECTION_FORWARD, None)

    hass.states.async_set(_STATE_INPUT_BOOLEAN, False)
    await hass.async_block_till_done()
    _verify(hass, STATE_OFF, None, 0, True, DIRECTION_FORWARD, None)


@pytest.mark.parametrize("count,domain", [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config,entity,tests",
    [
        (
            {
                DOMAIN: {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "value_template": "{{ 'on' }}",
                            "percentage_template": "{{ states('sensor.percentage') }}",
                            "turn_on": {"service": "script.fan_on"},
                            "turn_off": {"service": "script.fan_off"},
                        },
                    },
                }
            },
            "sensor.percentage",
            [
                ("0", 0, SPEED_OFF, None),
                ("33", 33, SPEED_LOW, None),
                ("invalid", 0, None, None),
                ("5000", 0, None, None),
                ("100", 100, SPEED_HIGH, None),
                ("0", 0, SPEED_OFF, None),
            ],
        ),
        (
            {
                DOMAIN: {
                    "platform": "template",
                    "fans": {
                        "test_fan": {
                            "value_template": "{{ 'on' }}",
                            "preset_modes": ["auto", "smart"],
                            "preset_mode_template": "{{ states('sensor.preset_mode') }}",
                            "turn_on": {"service": "script.fan_on"},
                            "turn_off": {"service": "script.fan_off"},
                        },
                    },
                }
            },
            "sensor.preset_mode",
            [
                ("0", None, None, None),
                ("invalid", None, None, None),
                ("auto", None, "auto", "auto"),
                ("smart", None, "smart", "smart"),
                ("invalid", None, None, None),
            ],
        ),
    ],
)
async def test_templates_with_entities2(hass, entity, tests, start_ha):
    """Test templates with values from other entities."""
    for set_percentage, test_percentage, speed, test_type in tests:
        hass.states.async_set(entity, set_percentage)
        await hass.async_block_till_done()
        _verify(hass, STATE_ON, speed, test_percentage, None, None, test_type)


@pytest.mark.parametrize("count,domain", [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
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
    ],
)
async def test_availability_template_with_entities(hass, start_ha):
    """Test availability tempalates with values from other entities."""
    for state, test_assert in [(STATE_ON, True), (STATE_OFF, False)]:
        hass.states.async_set(_STATE_AVAILABILITY_BOOLEAN, state)
        await hass.async_block_till_done()
        assert (hass.states.get(_TEST_FAN).state != STATE_UNAVAILABLE) == test_assert


@pytest.mark.parametrize("count,domain", [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config, states",
    [
        (
            {
                DOMAIN: {
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
            [STATE_OFF, None, None, None, None],
        ),
        (
            {
                DOMAIN: {
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
            [STATE_ON, None, 0, None, None],
        ),
        (
            {
                DOMAIN: {
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
            [STATE_ON, SPEED_MEDIUM, 66, True, DIRECTION_FORWARD],
        ),
        (
            {
                DOMAIN: {
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
            [STATE_OFF, None, 0, None, None],
        ),
    ],
)
async def test_template_with_unavailable_entities(hass, states, start_ha):
    """Test unavailability with value_template."""
    _verify(hass, states[0], states[1], states[2], states[3], states[4], None)


@pytest.mark.parametrize("count,domain", [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "fans": {
                    "test_fan": {
                        "value_template": "{{ 'on' }}",
                        "availability_template": "{{ x - 12 }}",
                        "speed_template": "{{ states('input_select.speed') }}",
                        "preset_mode_template": "{{ states('input_select.preset_mode') }}",
                        "oscillating_template": "{{ states('input_select.osc') }}",
                        "direction_template": "{{ states('input_select.direction') }}",
                        "turn_on": {"service": "script.fan_on"},
                        "turn_off": {"service": "script.fan_off"},
                    }
                },
            }
        },
    ],
)
async def test_invalid_availability_template_keeps_component_available(
    hass, start_ha, caplog_setup_text
):
    """Test that an invalid availability keeps the device available."""
    assert hass.states.get("fan.test_fan").state != STATE_UNAVAILABLE
    assert "TemplateError" in caplog_setup_text
    assert "x" in caplog_setup_text


async def test_on_off(hass):
    """Test turn on and turn off."""
    await _register_components(hass)

    for func, state in [
        (common.async_turn_on, STATE_ON),
        (common.async_turn_off, STATE_OFF),
    ]:
        await func(hass, _TEST_FAN)
        assert hass.states.get(_STATE_INPUT_BOOLEAN).state == state
        _verify(hass, state, None, 0, None, None, None)


async def test_set_speed(hass):
    """Test set valid speed."""
    await _register_components(hass, preset_modes=["auto", "smart"])

    await common.async_turn_on(hass, _TEST_FAN)
    for cmd, t_state, type, state, value in [
        (SPEED_HIGH, SPEED_HIGH, SPEED_HIGH, STATE_ON, 100),
        (SPEED_MEDIUM, SPEED_MEDIUM, SPEED_MEDIUM, STATE_ON, 66),
        (SPEED_OFF, SPEED_OFF, SPEED_OFF, STATE_OFF, 0),
        (SPEED_MEDIUM, SPEED_MEDIUM, SPEED_MEDIUM, STATE_ON, 66),
        ("invalid", SPEED_MEDIUM, SPEED_MEDIUM, STATE_ON, 66),
    ]:
        await common.async_set_speed(hass, _TEST_FAN, cmd)
        assert hass.states.get(_SPEED_INPUT_SELECT).state == t_state
        _verify(hass, state, type, value, None, None, None)


async def test_set_invalid_speed(hass):
    """Test set invalid speed when fan has valid speed."""
    await _register_components(hass)

    await common.async_turn_on(hass, _TEST_FAN)
    for extra in [SPEED_HIGH, "invalid"]:
        await common.async_set_speed(hass, _TEST_FAN, extra)
        assert hass.states.get(_SPEED_INPUT_SELECT).state == SPEED_HIGH
        _verify(hass, STATE_ON, SPEED_HIGH, 100, None, None, None)


async def test_custom_speed_list(hass):
    """Test set custom speed list."""
    await _register_components(hass, ["1", "2", "3"])

    await common.async_turn_on(hass, _TEST_FAN)
    for extra in ["1", SPEED_MEDIUM]:
        await common.async_set_speed(hass, _TEST_FAN, extra)
        assert hass.states.get(_SPEED_INPUT_SELECT).state == "1"
        _verify(hass, STATE_ON, "1", 33, None, None, None)


async def test_set_invalid_direction_from_initial_stage(hass, calls):
    """Test set invalid direction when fan is in initial state."""
    await _register_components(hass)

    await common.async_turn_on(hass, _TEST_FAN)

    await common.async_set_direction(hass, _TEST_FAN, "invalid")
    assert hass.states.get(_DIRECTION_INPUT_SELECT).state == ""
    _verify(hass, STATE_ON, None, 0, None, None, None)


async def test_set_osc(hass):
    """Test set oscillating."""
    await _register_components(hass)

    await common.async_turn_on(hass, _TEST_FAN)
    for state in [True, False]:
        await common.async_oscillate(hass, _TEST_FAN, state)
        assert hass.states.get(_OSC_INPUT).state == str(state)
        _verify(hass, STATE_ON, None, 0, state, None, None)


async def test_set_direction(hass):
    """Test set valid direction."""
    await _register_components(hass)

    await common.async_turn_on(hass, _TEST_FAN)
    for cmd in [DIRECTION_FORWARD, DIRECTION_REVERSE]:
        await common.async_set_direction(hass, _TEST_FAN, cmd)
        assert hass.states.get(_DIRECTION_INPUT_SELECT).state == cmd
        _verify(hass, STATE_ON, None, 0, None, cmd, None)


async def test_set_invalid_direction(hass):
    """Test set invalid direction when fan has valid direction."""
    await _register_components(hass)

    await common.async_turn_on(hass, _TEST_FAN)
    for cmd in [DIRECTION_FORWARD, "invalid"]:
        await common.async_set_direction(hass, _TEST_FAN, cmd)
        assert hass.states.get(_DIRECTION_INPUT_SELECT).state == DIRECTION_FORWARD
        _verify(hass, STATE_ON, None, 0, None, DIRECTION_FORWARD, None)


async def test_on_with_speed(hass):
    """Test turn on with speed."""
    await _register_components(hass)

    await common.async_turn_on(hass, _TEST_FAN, SPEED_HIGH)
    assert hass.states.get(_STATE_INPUT_BOOLEAN).state == STATE_ON
    assert int(float(hass.states.get(_PERCENTAGE_INPUT_NUMBER).state)) == 100
    _verify(hass, STATE_ON, SPEED_HIGH, 100, None, None, None)


async def test_preset_modes(hass):
    """Test preset_modes."""
    await _register_components(
        hass, ["off", "low", "medium", "high", "auto", "smart"], ["auto", "smart"]
    )

    await common.async_turn_on(hass, _TEST_FAN)
    for extra, state in [
        ("auto", "auto"),
        ("smart", "smart"),
        ("invalid", "smart"),
    ]:
        await common.async_set_preset_mode(hass, _TEST_FAN, extra)
        assert hass.states.get(_PRESET_MODE_INPUT_SELECT).state == state

    await common.async_turn_on(hass, _TEST_FAN, preset_mode="auto")
    assert hass.states.get(_PRESET_MODE_INPUT_SELECT).state == "auto"


async def test_set_percentage(hass):
    """Test set valid speed percentage."""
    await _register_components(hass)

    await common.async_turn_on(hass, _TEST_FAN)
    for type, state, value in [
        (SPEED_HIGH, STATE_ON, 100),
        (SPEED_MEDIUM, STATE_ON, 66),
        (SPEED_OFF, STATE_OFF, 0),
    ]:
        await common.async_set_percentage(hass, _TEST_FAN, value)
        assert int(float(hass.states.get(_PERCENTAGE_INPUT_NUMBER).state)) == value
        _verify(hass, state, type, value, None, None, None)

    await common.async_turn_on(hass, _TEST_FAN, percentage=50)
    assert int(float(hass.states.get(_PERCENTAGE_INPUT_NUMBER).state)) == 50
    _verify(hass, STATE_ON, SPEED_MEDIUM, 50, None, None, None)


async def test_increase_decrease_speed(hass):
    """Test set valid increase and decrease speed."""
    await _register_components(hass, speed_count=3)

    await common.async_turn_on(hass, _TEST_FAN)
    for func, extra, state, type, value in [
        (common.async_set_percentage, 100, STATE_ON, SPEED_HIGH, 100),
        (common.async_decrease_speed, None, STATE_ON, SPEED_MEDIUM, 66),
        (common.async_decrease_speed, None, STATE_ON, SPEED_LOW, 33),
        (common.async_decrease_speed, None, STATE_OFF, SPEED_OFF, 0),
        (common.async_increase_speed, None, STATE_ON, SPEED_LOW, 33),
    ]:
        await func(hass, _TEST_FAN, extra)
        assert int(float(hass.states.get(_PERCENTAGE_INPUT_NUMBER).state)) == value
        _verify(hass, state, type, value, None, None, None)


async def test_increase_decrease_speed_default_speed_count(hass):
    """Test set valid increase and decrease speed."""
    await _register_components(hass)

    await common.async_turn_on(hass, _TEST_FAN)
    for func, extra, state, type, value in [
        (common.async_set_percentage, 100, STATE_ON, SPEED_HIGH, 100),
        (common.async_decrease_speed, None, STATE_ON, SPEED_HIGH, 99),
        (common.async_decrease_speed, None, STATE_ON, SPEED_HIGH, 98),
        (common.async_decrease_speed, 31, STATE_ON, SPEED_HIGH, 67),
        (common.async_decrease_speed, None, STATE_ON, SPEED_MEDIUM, 66),
    ]:
        await func(hass, _TEST_FAN, extra)
        assert int(float(hass.states.get(_PERCENTAGE_INPUT_NUMBER).state)) == value
        _verify(hass, state, type, value, None, None, None)


async def test_set_invalid_osc_from_initial_state(hass):
    """Test set invalid oscillating when fan is in initial state."""
    await _register_components(hass)

    await common.async_turn_on(hass, _TEST_FAN)
    with pytest.raises(vol.Invalid):
        await common.async_oscillate(hass, _TEST_FAN, "invalid")
    assert hass.states.get(_OSC_INPUT).state == ""
    _verify(hass, STATE_ON, None, 0, None, None, None)


async def test_set_invalid_osc(hass):
    """Test set invalid oscillating when fan has valid osc."""
    await _register_components(hass)

    await common.async_turn_on(hass, _TEST_FAN)
    await common.async_oscillate(hass, _TEST_FAN, True)
    assert hass.states.get(_OSC_INPUT).state == "True"
    _verify(hass, STATE_ON, None, 0, True, None, None)

    with pytest.raises(vol.Invalid):
        await common.async_oscillate(hass, _TEST_FAN, None)
    assert hass.states.get(_OSC_INPUT).state == "True"
    _verify(hass, STATE_ON, None, 0, True, None, None)


def _verify(
    hass,
    expected_state,
    expected_speed,
    expected_percentage,
    expected_oscillating,
    expected_direction,
    expected_preset_mode,
):
    """Verify fan's state, speed and osc."""
    state = hass.states.get(_TEST_FAN)
    attributes = state.attributes
    assert state.state == str(expected_state)
    assert attributes.get(ATTR_SPEED) == expected_speed
    assert attributes.get(ATTR_PERCENTAGE) == expected_percentage
    assert attributes.get(ATTR_OSCILLATING) == expected_oscillating
    assert attributes.get(ATTR_DIRECTION) == expected_direction
    assert attributes.get(ATTR_PRESET_MODE) == expected_preset_mode


async def _register_components(
    hass, speed_list=None, preset_modes=None, speed_count=None
):
    """Register basic components for testing."""
    with assert_setup_component(1, "input_boolean"):
        assert await setup.async_setup_component(
            hass, "input_boolean", {"input_boolean": {"state": None}}
        )

    with assert_setup_component(1, "input_number"):
        assert await setup.async_setup_component(
            hass,
            "input_number",
            {
                "input_number": {
                    "percentage": {
                        "min": 0.0,
                        "max": 100.0,
                        "name": "Percentage",
                        "step": 1.0,
                        "mode": "slider",
                    }
                }
            },
        )

    with assert_setup_component(4, "input_select"):
        assert await setup.async_setup_component(
            hass,
            "input_select",
            {
                "input_select": {
                    "speed": {
                        "name": "Speed",
                        "options": [
                            "",
                            SPEED_OFF,
                            SPEED_LOW,
                            SPEED_MEDIUM,
                            SPEED_HIGH,
                            "1",
                            "2",
                            "3",
                            "auto",
                            "smart",
                        ],
                    },
                    "preset_mode": {
                        "name": "Preset Mode",
                        "options": ["auto", "smart"],
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
            "preset_mode_template": "{{ states('input_select.preset_mode') }}",
            "percentage_template": "{{ states('input_number.percentage') }}",
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
            "set_preset_mode": {
                "service": "input_select.select_option",
                "data_template": {
                    "entity_id": _PRESET_MODE_INPUT_SELECT,
                    "option": "{{ preset_mode }}",
                },
            },
            "set_percentage": {
                "service": "input_number.set_value",
                "data_template": {
                    "entity_id": _PERCENTAGE_INPUT_NUMBER,
                    "value": "{{ percentage }}",
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

        if preset_modes:
            test_fan_config["preset_modes"] = preset_modes

        if speed_count:
            test_fan_config["speed_count"] = speed_count

        assert await setup.async_setup_component(
            hass,
            "fan",
            {"fan": {"platform": "template", "fans": {"test_fan": test_fan_config}}},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


@pytest.mark.parametrize("count,domain", [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
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
            }
        },
    ],
)
async def test_unique_id(hass, start_ha):
    """Test unique_id option only creates one fan per id."""
    assert len(hass.states.async_all()) == 1


@pytest.mark.parametrize(
    "speed_count, percentage_step", [(0, 1), (100, 1), (3, 100 / 3)]
)
async def test_implemented_percentage(hass, speed_count, percentage_step):
    """Test a fan that implements percentage."""
    await setup.async_setup_component(
        hass,
        "fan",
        {
            "fan": {
                "platform": "template",
                "fans": {
                    "mechanical_ventilation": {
                        "friendly_name": "Mechanische ventilatie",
                        "unique_id": "a2fd2e38-674b-4b47-b5ef-cc2362211a72",
                        "value_template": "{{ states('light.mv_snelheid') }}",
                        "percentage_template": "{{ (state_attr('light.mv_snelheid','brightness') | int / 255 * 100) | int }}",
                        "turn_on": [
                            {
                                "service": "switch.turn_off",
                                "target": {
                                    "entity_id": "switch.mv_automatisch",
                                },
                            },
                            {
                                "service": "light.turn_on",
                                "target": {
                                    "entity_id": "light.mv_snelheid",
                                },
                                "data": {"brightness_pct": 40},
                            },
                        ],
                        "turn_off": [
                            {
                                "service": "light.turn_off",
                                "target": {
                                    "entity_id": "light.mv_snelheid",
                                },
                            },
                            {
                                "service": "switch.turn_on",
                                "target": {
                                    "entity_id": "switch.mv_automatisch",
                                },
                            },
                        ],
                        "set_percentage": [
                            {
                                "service": "light.turn_on",
                                "target": {
                                    "entity_id": "light.mv_snelheid",
                                },
                                "data": {"brightness_pct": "{{ percentage }}"},
                            }
                        ],
                        "speed_count": speed_count,
                    },
                },
            },
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    state = hass.states.get("fan.mechanical_ventilation")
    attributes = state.attributes
    assert attributes["percentage_step"] == percentage_step


@pytest.mark.parametrize("count,domain", [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "fans": {
                    "mechanical_ventilation": {
                        "friendly_name": "Mechanische ventilatie",
                        "unique_id": "a2fd2e38-674b-4b47-b5ef-cc2362211a72",
                        "value_template": "{{ states('light.mv_snelheid') }}",
                        "preset_mode_template": "{{ 'any' }}",
                        "preset_modes": ["any"],
                        "set_preset_mode": [
                            {
                                "service": "light.turn_on",
                                "target": {
                                    "entity_id": "light.mv_snelheid",
                                },
                                "data": {"brightness_pct": "{{ percentage }}"},
                            }
                        ],
                        "turn_on": [
                            {
                                "service": "switch.turn_off",
                                "target": {
                                    "entity_id": "switch.mv_automatisch",
                                },
                            },
                            {
                                "service": "light.turn_on",
                                "target": {
                                    "entity_id": "light.mv_snelheid",
                                },
                                "data": {"brightness_pct": 40},
                            },
                        ],
                        "turn_off": [
                            {
                                "service": "light.turn_off",
                                "target": {
                                    "entity_id": "light.mv_snelheid",
                                },
                            },
                            {
                                "service": "switch.turn_on",
                                "target": {
                                    "entity_id": "switch.mv_automatisch",
                                },
                            },
                        ],
                    },
                },
            }
        },
    ],
)
async def test_implemented_preset_mode(hass, start_ha):
    """Test a fan that implements preset_mode."""
    assert len(hass.states.async_all()) == 1

    state = hass.states.get("fan.mechanical_ventilation")
    attributes = state.attributes
    assert attributes["percentage"] is None


@pytest.mark.parametrize("count,domain", [(1, DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            DOMAIN: {
                "platform": "template",
                "fans": {
                    "mechanical_ventilation": {
                        "friendly_name": "Mechanische ventilatie",
                        "unique_id": "a2fd2e38-674b-4b47-b5ef-cc2362211a72",
                        "value_template": "{{ states('light.mv_snelheid') }}",
                        "speed_template": "{{ 'fast' }}",
                        "speeds": ["slow", "fast"],
                        "set_preset_mode": [
                            {
                                "service": "light.turn_on",
                                "target": {
                                    "entity_id": "light.mv_snelheid",
                                },
                                "data": {"brightness_pct": "{{ percentage }}"},
                            }
                        ],
                        "turn_on": [
                            {
                                "service": "switch.turn_off",
                                "target": {
                                    "entity_id": "switch.mv_automatisch",
                                },
                            },
                            {
                                "service": "light.turn_on",
                                "target": {
                                    "entity_id": "light.mv_snelheid",
                                },
                                "data": {"brightness_pct": 40},
                            },
                        ],
                        "turn_off": [
                            {
                                "service": "light.turn_off",
                                "target": {
                                    "entity_id": "light.mv_snelheid",
                                },
                            },
                            {
                                "service": "switch.turn_on",
                                "target": {
                                    "entity_id": "switch.mv_automatisch",
                                },
                            },
                        ],
                    },
                },
            }
        },
    ],
)
async def test_implemented_speed(hass, start_ha):
    """Test a fan that implements speed."""
    assert len(hass.states.async_all()) == 1

    state = hass.states.get("fan.mechanical_ventilation")
    attributes = state.attributes
    assert attributes["percentage"] == 100
    assert attributes["speed"] == "fast"
