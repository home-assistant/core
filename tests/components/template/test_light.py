"""The tests for the  Template light platform."""

import pytest

import homeassistant.components.light as light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_TRANSITION,
    SUPPORT_WHITE_VALUE,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)

# Represent for light's availability
_STATE_AVAILABILITY_BOOLEAN = "availability_boolean.state"


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "value_template": "{{states.test['big.fat...']}}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_template_state_invalid(
    hass, supported_features, supported_color_modes, start_ha
):
    """Test template state with render error."""
    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF
    assert "color_mode" not in state.attributes
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "value_template": "{{ states.light.test_state.state }}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_template_state_text(
    hass, supported_features, supported_color_modes, start_ha
):
    """Test the state text of a template."""
    set_state = STATE_ON
    hass.states.async_set("light.test_state", set_state)
    await hass.async_block_till_done()
    state = hass.states.get("light.test_template_light")
    assert state.state == set_state
    assert state.attributes["color_mode"] == ColorMode.UNKNOWN  # Brightness is None
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features

    set_state = STATE_OFF
    hass.states.async_set("light.test_state", set_state)
    await hass.async_block_till_done()
    state = hass.states.get("light.test_template_light")
    assert state.state == set_state
    assert "color_mode" not in state.attributes
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "config_addon,expected_state,expected_color_mode",
    [
        ({"replace1": '"{{ 1 == 1 }}"'}, STATE_ON, ColorMode.UNKNOWN),
        ({"replace1": '"{{ 1 == 2 }}"'}, STATE_OFF, None),
    ],
)
@pytest.mark.parametrize(
    "config",
    [
        """{
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "value_template": replace1,
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state"
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state"
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}"
                            }
                        }
                    }
                }
            }
        }""",
    ],
)
async def test_templatex_state_boolean(
    hass,
    expected_color_mode,
    expected_state,
    supported_features,
    supported_color_modes,
    start_ha,
):
    """Test the setting of the state with boolean on."""
    state = hass.states.get("light.test_template_light")
    assert state.state == expected_state
    assert state.attributes.get("color_mode") == expected_color_mode
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(0, light.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "value_template": "{%- if false -%}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                    }
                },
            }
        },
        {
            "light": {
                "platform": "template",
                "lights": {
                    "bad name here": {
                        "value_template": "{{ 1== 1}}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                    }
                },
            }
        },
        {
            "light": {
                "platform": "template",
                "switches": {"test_template_light": "Invalid"},
            }
        },
    ],
)
async def test_template_syntax_error(hass, start_ha):
    """Test templating syntax error."""
    assert hass.states.async_all("light") == []


SET_VAL1 = '"value_template": "{{ 1== 1}}",'
SET_VAL2 = '"turn_on": {"service": "light.turn_on","entity_id": "light.test_state"},'
SET_VAL3 = '"turn_off": {"service": "light.turn_off","entity_id": "light.test_state"},'


@pytest.mark.parametrize("domain", [light.DOMAIN])
@pytest.mark.parametrize(
    "config_addon, count",
    [
        ({"replace2": f"{SET_VAL2}{SET_VAL3}"}, 1),
        ({"replace2": f"{SET_VAL1}{SET_VAL2}"}, 0),
        ({"replace2": f"{SET_VAL2}{SET_VAL3}"}, 1),
    ],
)
@pytest.mark.parametrize(
    "config",
    [
        """{"light": {"platform": "template", "lights": {
            "light_one": {
                replace2
            "set_level": {"service": "light.turn_on",
            "data_template": {"entity_id": "light.test_state","brightness": "{{brightness}}"
        }}}}}}"""
    ],
)
async def test_missing_key(hass, count, start_ha):
    """Test missing template."""
    if count:
        assert hass.states.async_all("light") != []
    else:
        assert hass.states.async_all("light") == []


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "value_template": "{{states.light.test_state.state}}",
                        "turn_on": {"service": "test.automation"},
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_on_action(
    hass, start_ha, calls, supported_features, supported_color_modes
):
    """Test on action."""
    hass.states.async_set("light.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF
    assert "color_mode" not in state.attributes
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light"},
        blocking=True,
    )

    assert len(calls) == 1

    assert state.state == STATE_OFF
    assert "color_mode" not in state.attributes
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "value_template": "{{states.light.test_state.state}}",
                        "turn_on": {
                            "service": "test.automation",
                            "data_template": {
                                "transition": "{{transition}}",
                            },
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "supports_transition_template": "{{true}}",
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                                "transition": "{{transition}}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_on_action_with_transition(
    hass, start_ha, calls, supported_features, supported_color_modes
):
    """Test on action with transition."""
    hass.states.async_set("light.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF
    assert "color_mode" not in state.attributes
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_TRANSITION: 5},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["transition"] == 5

    assert state.state == STATE_OFF
    assert "color_mode" not in state.attributes
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes,expected_color_mode",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS], ColorMode.BRIGHTNESS)],
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "turn_on": {"service": "test.automation"},
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_on_action_optimistic(
    hass,
    start_ha,
    calls,
    supported_features,
    supported_color_modes,
    expected_color_mode,
):
    """Test on action with optimistic state."""
    hass.states.async_set("light.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF
    assert "color_mode" not in state.attributes
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light"},
        blocking=True,
    )

    state = hass.states.get("light.test_template_light")
    assert len(calls) == 1
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.UNKNOWN  # Brightness is None
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_BRIGHTNESS: 100},
        blocking=True,
    )

    state = hass.states.get("light.test_template_light")
    assert len(calls) == 1
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "value_template": "{{states.light.test_state.state}}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "test.automation",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_off_action(
    hass, start_ha, calls, supported_features, supported_color_modes
):
    """Test off action."""
    hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.UNKNOWN  # Brightness is None
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_template_light"},
        blocking=True,
    )

    assert len(calls) == 1
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.UNKNOWN  # Brightness is None
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "value_template": "{{states.light.test_state.state}}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "test.automation",
                            "data_template": {
                                "transition": "{{transition}}",
                            },
                        },
                        "supports_transition_template": "{{true}}",
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                                "transition": "{{transition}}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_off_action_with_transition(
    hass, start_ha, calls, supported_features, supported_color_modes
):
    """Test off action with transition."""
    hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.UNKNOWN  # Brightness is None
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_TRANSITION: 2},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["transition"] == 2
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.UNKNOWN  # Brightness is None
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {"service": "test.automation"},
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_off_action_optimistic(
    hass, start_ha, calls, supported_features, supported_color_modes
):
    """Test off action with optimistic state."""
    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF
    assert "color_mode" not in state.attributes
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_template_light"},
        blocking=True,
    )

    assert len(calls) == 1
    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF
    assert "color_mode" not in state.attributes
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes,expected_color_mode",
    [(SUPPORT_WHITE_VALUE, [ColorMode.RGBW], ColorMode.UNKNOWN)],
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "value_template": "{{1 == 1}}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_white_value": {
                            "service": "test.automation",
                            "data_template": {
                                "entity_id": "test.test_state",
                                "white_value": "{{white_value}}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_white_value_action_no_template(
    hass,
    start_ha,
    calls,
    supported_color_modes,
    supported_features,
    expected_color_mode,
):
    """Test setting white value with optimistic template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("white_value") is None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_WHITE_VALUE: 124},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["white_value"] == 124

    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("white_value") == 124
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode  # hs_color is None
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize(
    "expected_white_value,config_addon",
    [
        (255, {"replace3": "{{255}}"}),
        (None, {"replace3": "{{256}}"}),
        (None, {"replace3": "{{x - 12}}"}),
        (None, {"replace3": "{{ none }}"}),
        (None, {"replace3": ""}),
    ],
)
@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes,expected_color_mode",
    [(SUPPORT_WHITE_VALUE, [ColorMode.RGBW], ColorMode.UNKNOWN)],
)
@pytest.mark.parametrize(
    "config",
    [
        """{
            "light": {"platform": "template","lights": {
                "test_template_light": {
                "value_template": "{{ 1 == 1 }}",
                "turn_on": {"service": "light.turn_on","entity_id": "light.test_state"},
                "turn_off": {"service": "light.turn_off","entity_id": "light.test_state"},
                "set_white_value": {"service": "light.turn_on",
                    "data_template": {"entity_id": "light.test_state",
                        "white_value": "{{white_value}}"}},
                    "white_value_template": "replace3"
        }}}}""",
    ],
)
async def test_white_value_template(
    hass,
    expected_white_value,
    start_ha,
    supported_features,
    supported_color_modes,
    expected_color_mode,
):
    """Test the template for the white value."""
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("white_value") == expected_white_value
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode  # hs_color is None
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes,expected_color_mode",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS], ColorMode.BRIGHTNESS)],
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "value_template": "{{1 == 1}}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "test.automation",
                            "data_template": {
                                "entity_id": "test.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_level_action_no_template(
    hass,
    start_ha,
    calls,
    supported_features,
    supported_color_modes,
    expected_color_mode,
):
    """Test setting brightness with optimistic template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("brightness") is None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_BRIGHTNESS: 124},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["brightness"] == 124

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 124
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "expected_level,config_addon,expected_color_mode",
    [
        (255, {"replace4": '"{{255}}"'}, ColorMode.BRIGHTNESS),
        (None, {"replace4": '"{{256}}"'}, ColorMode.UNKNOWN),
        (None, {"replace4": '"{{x - 12}}"'}, ColorMode.UNKNOWN),
        (None, {"replace4": '"{{ none }}"'}, ColorMode.UNKNOWN),
        (None, {"replace4": '""'}, ColorMode.UNKNOWN),
        (
            None,
            {"replace4": "\"{{ state_attr('light.nolight', 'brightness') }}\""},
            ColorMode.UNKNOWN,
        ),
    ],
)
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "config",
    [
        """{"light": {"platform": "template", "lights": {
            "test_template_light": {
                "value_template": "{{ 1 == 1 }}",
                "turn_on": {"service": "light.turn_on","entity_id": "light.test_state"},
                "turn_off": {"service": "light.turn_off","entity_id": "light.test_state"},
                "set_level": {"service": "light.turn_on","data_template": {
                    "entity_id": "light.test_state","brightness": "{{brightness}}"}},
                "level_template": replace4
        }}}}""",
    ],
)
async def test_level_template(
    hass,
    expected_level,
    start_ha,
    supported_features,
    supported_color_modes,
    expected_color_mode,
):
    """Test the template for the level."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("brightness") == expected_level
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "expected_temp,config_addon,expected_color_mode",
    [
        (500, {"replace5": '"{{500}}"'}, ColorMode.COLOR_TEMP),
        (None, {"replace5": '"{{501}}"'}, ColorMode.UNKNOWN),
        (None, {"replace5": '"{{x - 12}}"'}, ColorMode.UNKNOWN),
        (None, {"replace5": '"None"'}, ColorMode.UNKNOWN),
        (None, {"replace5": '"{{ none }}"'}, ColorMode.UNKNOWN),
        (None, {"replace5": '""'}, ColorMode.UNKNOWN),
    ],
)
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_COLOR_TEMP, [ColorMode.COLOR_TEMP])],
)
@pytest.mark.parametrize(
    "config",
    [
        """{
                "light": {
                    "platform": "template",
                    "lights": {
                        "test_template_light": {
                            "value_template": "{{ 1 == 1 }}",
                            "turn_on": {
                                "service": "light.turn_on",
                                "entity_id": "light.test_state"
                            },
                            "turn_off": {
                                "service": "light.turn_off",
                                "entity_id": "light.test_state"
                            },
                            "set_temperature": {
                                "service": "light.turn_on",
                                "data_template": {
                                    "entity_id": "light.test_state",
                                    "color_temp": "{{color_temp}}"
                                }
                            },
                            "temperature_template": replace5
                        }
                    }
                }
            }"""
    ],
)
async def test_temperature_template(
    hass,
    expected_temp,
    start_ha,
    supported_features,
    supported_color_modes,
    expected_color_mode,
):
    """Test the template for the temperature."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("color_temp") == expected_temp
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes,expected_color_mode",
    [(SUPPORT_COLOR_TEMP, [ColorMode.COLOR_TEMP], ColorMode.COLOR_TEMP)],
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "value_template": "{{1 == 1}}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_temperature": {
                            "service": "test.automation",
                            "data_template": {
                                "entity_id": "test.test_state",
                                "color_temp": "{{color_temp}}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_temperature_action_no_template(
    hass,
    start_ha,
    calls,
    supported_features,
    supported_color_modes,
    expected_color_mode,
):
    """Test setting temperature with optimistic template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("color_template") is None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_COLOR_TEMP: 345},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["color_temp"] == 345

    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("color_temp") == 345
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "friendly_name": "Template light",
                        "value_template": "{{ 1 == 1 }}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_friendly_name(hass, start_ha):
    """Test the accessibility of the friendly_name attribute."""

    state = hass.states.get("light.test_template_light")
    assert state is not None

    assert state.attributes.get("friendly_name") == "Template light"


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "friendly_name": "Template light",
                        "value_template": "{{ 1 == 1 }}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                        "icon_template": "{% if states.light.test_state.state %}"
                        "mdi:check"
                        "{% endif %}",
                    }
                },
            }
        },
    ],
)
async def test_icon_template(hass, start_ha):
    """Test icon template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("icon") == ""

    state = hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")

    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "friendly_name": "Template light",
                        "value_template": "{{ 1 == 1 }}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                        "entity_picture_template": "{% if states.light.test_state.state %}"
                        "/local/light.png"
                        "{% endif %}",
                    }
                },
            }
        },
    ],
)
async def test_entity_picture_template(hass, start_ha):
    """Test entity_picture template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("entity_picture") == ""

    state = hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")

    assert state.attributes["entity_picture"] == "/local/light.png"


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes, expected_color_mode",
    [(SUPPORT_COLOR, [ColorMode.HS], ColorMode.UNKNOWN)],
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "value_template": "{{1 == 1}}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_color": [
                            {
                                "service": "test.automation",
                                "data_template": {
                                    "entity_id": "test.test_state",
                                    "h": "{{h}}",
                                    "s": "{{s}}",
                                },
                            },
                            {
                                "service": "test.automation",
                                "data_template": {
                                    "entity_id": "test.test_state",
                                    "s": "{{s}}",
                                    "h": "{{h}}",
                                },
                            },
                        ],
                    }
                },
            }
        },
    ],
)
async def test_color_action_no_template(
    hass,
    start_ha,
    calls,
    supported_features,
    supported_color_modes,
    expected_color_mode,
):
    """Test setting color with optimistic template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("hs_color") is None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_HS_COLOR: (40, 50)},
        blocking=True,
    )

    assert len(calls) == 2
    assert calls[0].data["h"] == 40
    assert calls[0].data["s"] == 50
    assert calls[1].data["h"] == 40
    assert calls[1].data["s"] == 50

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode  # hs_color is None
    assert "hs_color" not in state.attributes
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "expected_hs,config_addon,expected_color_mode",
    [
        ((360, 100), {"replace6": '"{{(360, 100)}}"'}, ColorMode.HS),
        ((359.9, 99.9), {"replace6": '"{{(359.9, 99.9)}}"'}, ColorMode.HS),
        (None, {"replace6": '"{{(361, 100)}}"'}, ColorMode.UNKNOWN),
        (None, {"replace6": '"{{(360, 101)}}"'}, ColorMode.UNKNOWN),
        (None, {"replace6": '"[{{(360)}},{{null}}]"'}, ColorMode.UNKNOWN),
        (None, {"replace6": '"{{x - 12}}"'}, ColorMode.UNKNOWN),
        (None, {"replace6": '""'}, ColorMode.UNKNOWN),
        (None, {"replace6": '"{{ none }}"'}, ColorMode.UNKNOWN),
    ],
)
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_COLOR, [ColorMode.HS])],
)
@pytest.mark.parametrize(
    "config",
    [
        """{"light": {"platform": "template","lights": {"test_template_light": {
            "value_template": "{{ 1 == 1 }}",
            "turn_on": {"service": "light.turn_on","entity_id": "light.test_state"},
            "turn_off": {"service": "light.turn_off","entity_id": "light.test_state"},
            "set_color": [{"service": "input_number.set_value",
                "data_template": {"entity_id": "input_number.h","color_temp": "{{h}}"
                }}],
            "color_template": replace6
        }}}}"""
    ],
)
async def test_color_template(
    hass,
    expected_hs,
    start_ha,
    supported_features,
    supported_color_modes,
    expected_color_mode,
):
    """Test the template for the color."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("hs_color") == expected_hs
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "value_template": "{{true}}",
                        "turn_on": {"service": "test.automation"},
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                        "set_effect": {
                            "service": "test.automation",
                            "data_template": {
                                "entity_id": "test.test_state",
                                "effect": "{{effect}}",
                            },
                        },
                        "effect_list_template": "{{ ['Disco', 'Police'] }}",
                        "effect_template": "{{ 'Disco' }}",
                    }
                },
            }
        },
    ],
)
async def test_effect_action_valid_effect(hass, start_ha, calls):
    """Test setting valid effect with template."""
    state = hass.states.get("light.test_template_light")
    assert state is not None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_EFFECT: "Disco"},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["effect"] == "Disco"

    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("effect") == "Disco"


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "value_template": "{{true}}",
                        "turn_on": {"service": "test.automation"},
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                        "set_effect": {
                            "service": "test.automation",
                            "data_template": {
                                "entity_id": "test.test_state",
                                "effect": "{{effect}}",
                            },
                        },
                        "effect_list_template": "{{ ['Disco', 'Police'] }}",
                        "effect_template": "{{ None }}",
                    }
                },
            }
        },
    ],
)
async def test_effect_action_invalid_effect(hass, start_ha, calls):
    """Test setting invalid effect with template."""
    state = hass.states.get("light.test_template_light")
    assert state is not None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_EFFECT: "RGB"},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["effect"] == "RGB"

    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("effect") is None


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "expected_effect_list,config_addon",
    [
        (
            ["Strobe color", "Police", "Christmas", "RGB", "Random Loop"],
            {
                "replace7": "\"{{ ['Strobe color', 'Police', 'Christmas', 'RGB', 'Random Loop'] }}\""
            },
        ),
        (
            ["Police", "RGB", "Random Loop"],
            {"replace7": "\"{{ ['Police', 'RGB', 'Random Loop'] }}\""},
        ),
        (None, {"replace7": '"{{ [] }}"'}),
        (None, {"replace7": "\"{{ '[]' }}\""}),
        (None, {"replace7": '"{{ 124 }}"'}),
        (None, {"replace7": "\"{{ '124' }}\""}),
        (None, {"replace7": '"{{ none }}"'}),
        (None, {"replace7": '""'}),
    ],
)
@pytest.mark.parametrize(
    "config",
    [
        """{"light": {"platform": "template","lights": {"test_template_light": {
            "value_template": "{{ 1 == 1 }}",
            "turn_on": {"service": "light.turn_on","entity_id": "light.test_state"},
            "turn_off": {"service": "light.turn_off","entity_id": "light.test_state"},
            "set_effect": {"service": "test.automation",
                "data_template": {"entity_id": "test.test_state","effect": "{{effect}}"}},
            "effect_template": "{{ None }}",
            "effect_list_template": replace7
        }}}}""",
    ],
)
async def test_effect_list_template(hass, expected_effect_list, start_ha):
    """Test the template for the effect list."""
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("effect_list") == expected_effect_list


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "expected_effect,config_addon",
    [
        (None, {"replace8": '"Disco"'}),
        (None, {"replace8": '"None"'}),
        (None, {"replace8": '"{{ None }}"'}),
        ("Police", {"replace8": '"Police"'}),
        ("Strobe color", {"replace8": "\"{{ 'Strobe color' }}\""}),
    ],
)
@pytest.mark.parametrize(
    "config",
    [
        """{"light": {"platform": "template","lights": {"test_template_light": {
            "value_template": "{{ 1 == 1 }}",
            "turn_on": {"service": "light.turn_on","entity_id": "light.test_state"},
            "turn_off": {"service": "light.turn_off","entity_id": "light.test_state"},
            "set_effect": {"service": "test.automation","data_template": {
                "entity_id": "test.test_state","effect": "{{effect}}"}},
            "effect_list_template": "{{ ['Strobe color', 'Police', 'Christmas', 'RGB', 'Random Loop'] }}",
            "effect_template": replace8
        }}}}""",
    ],
)
async def test_effect_template(hass, expected_effect, start_ha):
    """Test the template for the effect."""
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("effect") == expected_effect


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "expected_min_mireds,config_addon",
    [
        (118, {"replace9": '"{{118}}"'}),
        (153, {"replace9": '"{{x - 12}}"'}),
        (153, {"replace9": '"None"'}),
        (153, {"replace9": '"{{ none }}"'}),
        (153, {"replace9": '""'}),
        (153, {"replace9": "\"{{ 'a' }}\""}),
    ],
)
@pytest.mark.parametrize(
    "config",
    [
        """{"light": {"platform": "template","lights": {"test_template_light": {
            "value_template": "{{ 1 == 1 }}",
            "turn_on": {"service": "light.turn_on","entity_id": "light.test_state"},
            "turn_off": {"service": "light.turn_off","entity_id": "light.test_state"},
            "set_temperature": {"service": "light.turn_on","data_template": {
                "entity_id": "light.test_state","color_temp": "{{color_temp}}"}},
            "temperature_template": "{{200}}",
            "min_mireds_template": replace9
        }}}}""",
    ],
)
async def test_min_mireds_template(hass, expected_min_mireds, start_ha):
    """Test the template for the min mireds."""
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("min_mireds") == expected_min_mireds


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "expected_max_mireds,config_addon",
    [
        (488, {"template1": '"{{488}}"'}),
        (500, {"template1": '"{{x - 12}}"'}),
        (500, {"template1": '"None"'}),
        (500, {"template1": '"{{ none }}"'}),
        (500, {"template1": '""'}),
        (500, {"template1": "\"{{ 'a' }}\""}),
    ],
)
@pytest.mark.parametrize(
    "config",
    [
        """{"light": {"platform": "template","lights": {"test_template_light": {
            "value_template": "{{ 1 == 1 }}",
            "turn_on": {"service": "light.turn_on","entity_id": "light.test_state"},
            "turn_off": {"service": "light.turn_off","entity_id": "light.test_state"},
            "set_temperature": {"service": "light.turn_on","data_template": {
                "entity_id": "light.test_state","color_temp": "{{color_temp}}"}},
            "temperature_template": "{{200}}",
            "max_mireds_template": template1
        }}}}""",
    ],
)
async def test_max_mireds_template(hass, expected_max_mireds, start_ha):
    """Test the template for the max mireds."""
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("max_mireds") == expected_max_mireds


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "expected_supports_transition,config_addon",
    [
        (True, {"template2": '"{{true}}"'}),
        (True, {"template2": '"{{1 == 1}}"'}),
        (False, {"template2": '"{{false}}"'}),
        (False, {"template2": '"{{ none }}"'}),
        (False, {"template2": '""'}),
        (False, {"template2": '"None"'}),
    ],
)
@pytest.mark.parametrize(
    "config",
    [
        """{"light": {"platform": "template","lights": {"test_template_light": {
            "value_template": "{{ 1 == 1 }}",
            "turn_on": {"service": "light.turn_on","entity_id": "light.test_state"},
            "turn_off": {"service": "light.turn_off","entity_id": "light.test_state"},
            "set_temperature": {"service": "light.turn_on","data_template": {
                "entity_id": "light.test_state","color_temp": "{{color_temp}}"}},
                "supports_transition_template": template2
        }}}}""",
    ],
)
async def test_supports_transition_template(
    hass, expected_supports_transition, start_ha
):
    """Test the template for the supports transition."""
    state = hass.states.get("light.test_template_light")

    expected_value = 1

    if expected_supports_transition is True:
        expected_value = 0

    assert state is not None
    assert (
        int(state.attributes.get("supported_features")) & LightEntityFeature.TRANSITION
    ) != expected_value


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "availability_template": "{{ is_state('availability_boolean.state', 'on') }}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
                    }
                },
            }
        },
    ],
)
async def test_available_template_with_entities(hass, start_ha):
    """Test availability templates with values from other entities."""
    # When template returns true..
    hass.states.async_set(_STATE_AVAILABILITY_BOOLEAN, STATE_ON)
    await hass.async_block_till_done()

    # Device State should not be unavailable
    assert hass.states.get("light.test_template_light").state != STATE_UNAVAILABLE

    # When Availability template returns false
    hass.states.async_set(_STATE_AVAILABILITY_BOOLEAN, STATE_OFF)
    await hass.async_block_till_done()

    # device state should be unavailable
    assert hass.states.get("light.test_template_light").state == STATE_UNAVAILABLE


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light": {
                        "availability_template": "{{ x - 12 }}",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                        "set_level": {
                            "service": "light.turn_on",
                            "data_template": {
                                "entity_id": "light.test_state",
                                "brightness": "{{brightness}}",
                            },
                        },
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
    assert hass.states.get("light.test_template_light").state != STATE_UNAVAILABLE
    assert ("UndefinedError: 'x' is undefined") in caplog_setup_text


@pytest.mark.parametrize("count,domain", [(1, light.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "light": {
                "platform": "template",
                "lights": {
                    "test_template_light_01": {
                        "unique_id": "not-so-unique-anymore",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                    },
                    "test_template_light_02": {
                        "unique_id": "not-so-unique-anymore",
                        "turn_on": {
                            "service": "light.turn_on",
                            "entity_id": "light.test_state",
                        },
                        "turn_off": {
                            "service": "light.turn_off",
                            "entity_id": "light.test_state",
                        },
                    },
                },
            }
        },
    ],
)
async def test_unique_id(hass, start_ha):
    """Test unique_id option only creates one light per id."""
    assert len(hass.states.async_all("light")) == 1
