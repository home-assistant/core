"""The tests for the  Template light platform."""

import pytest

import homeassistant.components.light as light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_TRANSITION,
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
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component

# Represent for light's availability
_STATE_AVAILABILITY_BOOLEAN = "availability_boolean.state"


OPTIMISTIC_ON_OFF_LIGHT_CONFIG = {
    "turn_on": {
        "service": "test.automation",
        "data_template": {
            "action": "turn_on",
            "caller": "{{ this.entity_id }}",
        },
    },
    "turn_off": {
        "service": "test.automation",
        "data_template": {
            "action": "turn_off",
            "caller": "{{ this.entity_id }}",
        },
    },
}


OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG = {
    **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
    "set_level": {
        "service": "test.automation",
        "data_template": {
            "action": "set_level",
            "brightness": "{{brightness}}",
            "caller": "{{ this.entity_id }}",
        },
    },
}


OPTIMISTIC_COLOR_TEMP_LIGHT_CONFIG = {
    **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
    "set_temperature": {
        "service": "test.automation",
        "data_template": {
            "action": "set_temperature",
            "caller": "{{ this.entity_id }}",
            "color_temp": "{{color_temp}}",
        },
    },
}


OPTIMISTIC_HS_COLOR_LIGHT_CONFIG = {
    **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
    "set_color": {
        "service": "test.automation",
        "data_template": {
            "action": "set_color",
            "caller": "{{ this.entity_id }}",
            "s": "{{s}}",
            "h": "{{h}}",
        },
    },
}


async def async_setup_light(hass, count, light_config):
    """Do setup of light integration."""
    config = {"light": {"platform": "template", "lights": light_config}}

    with assert_setup_component(count, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


@pytest.fixture
async def setup_light(hass, count, light_config):
    """Do setup of light integration."""
    await async_setup_light(hass, count, light_config)


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "value_template": "{{states.test['big.fat...']}}",
            }
        },
    ],
)
async def test_template_state_invalid(
    hass, supported_features, supported_color_modes, setup_light
):
    """Test template state with render error."""
    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF
    assert "color_mode" not in state.attributes
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "value_template": "{{ states.light.test_state.state }}",
            }
        },
    ],
)
async def test_template_state_text(
    hass, supported_features, supported_color_modes, setup_light
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


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "value_template,expected_state,expected_color_mode",
    [
        (
            "{{ 1 == 1 }}",
            STATE_ON,
            ColorMode.UNKNOWN,
        ),
        (
            "{{ 1 == 2 }}",
            STATE_OFF,
            None,
        ),
    ],
)
async def test_templatex_state_boolean(
    hass,
    expected_color_mode,
    expected_state,
    supported_features,
    supported_color_modes,
    count,
    value_template,
):
    """Test the setting of the state with boolean on."""
    light_config = {
        "test_template_light": {
            **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
            "value_template": value_template,
        }
    }
    await async_setup_light(hass, count, light_config)
    state = hass.states.get("light.test_template_light")
    assert state.state == expected_state
    assert state.attributes.get("color_mode") == expected_color_mode
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count", [0])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "value_template": "{%- if false -%}",
            }
        },
        {
            "bad name here": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "value_template": "{{ 1== 1}}",
            }
        },
        {"test_template_light": "Invalid"},
    ],
)
async def test_template_syntax_error(hass, setup_light):
    """Test templating syntax error."""
    assert hass.states.async_all("light") == []


@pytest.mark.parametrize(
    "light_config, count",
    [
        (
            {
                "light_one": {
                    "value_template": "{{ 1== 1}}",
                    "turn_on": {
                        "service": "light.turn_on",
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
            0,
        ),
    ],
)
async def test_missing_key(hass, count, setup_light):
    """Test missing template."""
    if count:
        assert hass.states.async_all("light") != []
    else:
        assert hass.states.async_all("light") == []


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "value_template": "{{states.light.test_state.state}}",
            }
        },
    ],
)
async def test_on_action(
    hass, setup_light, calls, supported_features, supported_color_modes
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
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == "light.test_template_light"

    assert state.state == STATE_OFF
    assert "color_mode" not in state.attributes
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "light_config",
    [
        {
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
    ],
)
async def test_on_action_with_transition(
    hass, setup_light, calls, supported_features, supported_color_modes
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


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes,expected_color_mode",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS], ColorMode.BRIGHTNESS)],
)
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
            }
        },
    ],
)
async def test_on_action_optimistic(
    hass,
    setup_light,
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
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == "light.test_template_light"
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
    assert len(calls) == 2
    assert calls[-1].data["action"] == "set_level"
    assert calls[-1].data["brightness"] == 100
    assert calls[-1].data["caller"] == "light.test_template_light"
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "value_template": "{{states.light.test_state.state}}",
            }
        },
    ],
)
async def test_off_action(
    hass, setup_light, calls, supported_features, supported_color_modes
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
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == "light.test_template_light"
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.UNKNOWN  # Brightness is None
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count", [(1)])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "light_config",
    [
        {
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
    ],
)
async def test_off_action_with_transition(
    hass, setup_light, calls, supported_features, supported_color_modes
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


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
            }
        },
    ],
)
async def test_off_action_optimistic(
    hass, setup_light, calls, supported_features, supported_color_modes
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


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes,expected_color_mode",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS], ColorMode.BRIGHTNESS)],
)
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "value_template": "{{1 == 1}}",
            }
        },
    ],
)
async def test_level_action_no_template(
    hass,
    setup_light,
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
    assert calls[-1].data["action"] == "set_level"
    assert calls[-1].data["brightness"] == 124
    assert calls[-1].data["caller"] == "light.test_template_light"

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 124
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "expected_level,level_template,expected_color_mode",
    [
        (255, "{{255}}", ColorMode.BRIGHTNESS),
        (None, "{{256}}", ColorMode.UNKNOWN),
        (None, "{{x - 12}}", ColorMode.UNKNOWN),
        (None, "{{ none }}", ColorMode.UNKNOWN),
        (None, "", ColorMode.UNKNOWN),
        (
            None,
            "{{ state_attr('light.nolight', 'brightness') }}",
            ColorMode.UNKNOWN,
        ),
    ],
)
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_BRIGHTNESS, [ColorMode.BRIGHTNESS])],
)
async def test_level_template(
    hass,
    expected_level,
    supported_features,
    supported_color_modes,
    expected_color_mode,
    count,
    level_template,
):
    """Test the template for the level."""
    light_config = {
        "test_template_light": {
            **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
            "value_template": "{{ 1 == 1 }}",
            "level_template": level_template,
        }
    }
    await async_setup_light(hass, count, light_config)
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("brightness") == expected_level
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "expected_temp,temperature_template,expected_color_mode",
    [
        (500, "{{500}}", ColorMode.COLOR_TEMP),
        (None, "{{501}}", ColorMode.UNKNOWN),
        (None, "{{x - 12}}", ColorMode.UNKNOWN),
        (None, "None", ColorMode.UNKNOWN),
        (None, "{{ none }}", ColorMode.UNKNOWN),
        (None, "", ColorMode.UNKNOWN),
    ],
)
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_COLOR_TEMP, [ColorMode.COLOR_TEMP])],
)
async def test_temperature_template(
    hass,
    expected_temp,
    supported_features,
    supported_color_modes,
    expected_color_mode,
    count,
    temperature_template,
):
    """Test the template for the temperature."""
    light_config = {
        "test_template_light": {
            **OPTIMISTIC_COLOR_TEMP_LIGHT_CONFIG,
            "value_template": "{{ 1 == 1 }}",
            "temperature_template": temperature_template,
        }
    }
    await async_setup_light(hass, count, light_config)
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("color_temp") == expected_temp
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes,expected_color_mode",
    [(SUPPORT_COLOR_TEMP, [ColorMode.COLOR_TEMP], ColorMode.COLOR_TEMP)],
)
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_COLOR_TEMP_LIGHT_CONFIG,
                "value_template": "{{1 == 1}}",
            }
        },
    ],
)
async def test_temperature_action_no_template(
    hass,
    setup_light,
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
    assert calls[-1].data["action"] == "set_temperature"
    assert calls[-1].data["caller"] == "light.test_template_light"
    assert calls[-1].data["color_temp"] == 345

    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("color_temp") == 345
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "friendly_name": "Template light",
                "value_template": "{{ 1 == 1 }}",
            }
        },
    ],
)
async def test_friendly_name(hass, setup_light):
    """Test the accessibility of the friendly_name attribute."""

    state = hass.states.get("light.test_template_light")
    assert state is not None

    assert state.attributes.get("friendly_name") == "Template light"


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "friendly_name": "Template light",
                "value_template": "{{ 1 == 1 }}",
                "icon_template": "{% if states.light.test_state.state %}"
                "mdi:check"
                "{% endif %}",
            }
        },
    ],
)
async def test_icon_template(hass, setup_light):
    """Test icon template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("icon") == ""

    state = hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")

    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "friendly_name": "Template light",
                "value_template": "{{ 1 == 1 }}",
                "entity_picture_template": "{% if states.light.test_state.state %}"
                "/local/light.png"
                "{% endif %}",
            }
        },
    ],
)
async def test_entity_picture_template(hass, setup_light):
    """Test entity_picture template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("entity_picture") == ""

    state = hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")

    assert state.attributes["entity_picture"] == "/local/light.png"


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes, expected_color_mode",
    [(SUPPORT_COLOR, [ColorMode.HS], ColorMode.HS)],
)
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_HS_COLOR_LIGHT_CONFIG,
                "value_template": "{{1 == 1}}",
            }
        },
    ],
)
async def test_color_action_no_template(
    hass,
    setup_light,
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

    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_color"
    assert calls[-1].data["caller"] == "light.test_template_light"
    assert calls[-1].data["h"] == 40
    assert calls[-1].data["s"] == 50

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes.get("hs_color") == (40, 50)
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "expected_hs,color_template,expected_color_mode",
    [
        ((360, 100), "{{(360, 100)}}", ColorMode.HS),
        ((359.9, 99.9), "{{(359.9, 99.9)}}", ColorMode.HS),
        (None, "{{(361, 100)}}", ColorMode.UNKNOWN),
        (None, "{{(360, 101)}}", ColorMode.UNKNOWN),
        (None, "[{{(360)}},{{null}}]", ColorMode.UNKNOWN),
        (None, "{{x - 12}}", ColorMode.UNKNOWN),
        (None, "", ColorMode.UNKNOWN),
        (None, "{{ none }}", ColorMode.UNKNOWN),
    ],
)
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_COLOR, [ColorMode.HS])],
)
async def test_color_template(
    hass,
    expected_hs,
    supported_features,
    supported_color_modes,
    expected_color_mode,
    count,
    color_template,
):
    """Test the template for the color."""
    light_config = {
        "test_template_light": {
            **OPTIMISTIC_HS_COLOR_LIGHT_CONFIG,
            "value_template": "{{ 1 == 1 }}",
            "color_template": color_template,
        }
    }
    await async_setup_light(hass, count, light_config)
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("hs_color") == expected_hs
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "supported_features,supported_color_modes",
    [(SUPPORT_COLOR | SUPPORT_COLOR_TEMP, [ColorMode.COLOR_TEMP, ColorMode.HS])],
)
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                "value_template": "{{1 == 1}}",
                "set_color": [
                    {
                        "service": "test.automation",
                        "data_template": {
                            "entity_id": "test.test_state",
                            "h": "{{h}}",
                            "s": "{{s}}",
                        },
                    },
                ],
                "set_temperature": {
                    "service": "test.automation",
                    "data_template": {
                        "entity_id": "test.test_state",
                        "color_temp": "{{color_temp}}",
                    },
                },
            }
        },
    ],
)
async def test_color_and_temperature_actions_no_template(
    hass, setup_light, calls, supported_features, supported_color_modes
):
    """Test setting color and color temperature with optimistic template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("hs_color") is None

    # Optimistically set color, light should be in hs_color mode
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_HS_COLOR: (40, 50)},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[-1].data["h"] == 40
    assert calls[-1].data["s"] == 50

    state = hass.states.get("light.test_template_light")
    assert state.attributes["color_mode"] == ColorMode.HS
    assert "color_temp" not in state.attributes
    assert state.attributes["hs_color"] == (40, 50)
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features

    # Optimistically set color temp, light should be in color temp mode
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_COLOR_TEMP: 123},
        blocking=True,
    )

    assert len(calls) == 2
    assert calls[-1].data["color_temp"] == 123

    state = hass.states.get("light.test_template_light")
    assert state.attributes["color_mode"] == ColorMode.COLOR_TEMP
    assert state.attributes["color_temp"] == 123
    assert "hs_color" in state.attributes  # Color temp represented as hs_color
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features

    # Optimistically set color, light should again be in hs_color mode
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_HS_COLOR: (10, 20)},
        blocking=True,
    )

    assert len(calls) == 3
    assert calls[-1].data["h"] == 10
    assert calls[-1].data["s"] == 20

    state = hass.states.get("light.test_template_light")
    assert state.attributes["color_mode"] == ColorMode.HS
    assert "color_temp" not in state.attributes
    assert state.attributes["hs_color"] == (10, 20)
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features

    # Optimistically set color temp, light should again be in color temp mode
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_COLOR_TEMP: 234},
        blocking=True,
    )

    assert len(calls) == 4
    assert calls[-1].data["color_temp"] == 234

    state = hass.states.get("light.test_template_light")
    assert state.attributes["color_mode"] == ColorMode.COLOR_TEMP
    assert state.attributes["color_temp"] == 234
    assert "hs_color" in state.attributes  # Color temp represented as hs_color
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "value_template": "{{true}}",
                "set_effect": {
                    "service": "test.automation",
                    "data_template": {
                        "action": "set_effect",
                        "caller": "{{ this.entity_id }}",
                        "entity_id": "test.test_state",
                        "effect": "{{effect}}",
                    },
                },
                "effect_list_template": "{{ ['Disco', 'Police'] }}",
                "effect_template": "{{ 'Disco' }}",
            }
        },
    ],
)
async def test_effect_action_valid_effect(hass, setup_light, calls):
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
    assert calls[-1].data["action"] == "set_effect"
    assert calls[-1].data["caller"] == "light.test_template_light"
    assert calls[-1].data["effect"] == "Disco"

    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("effect") == "Disco"


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "value_template": "{{true}}",
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
    ],
)
async def test_effect_action_invalid_effect(hass, setup_light, calls):
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


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "expected_effect_list,effect_list_template",
    [
        (
            ["Strobe color", "Police", "Christmas", "RGB", "Random Loop"],
            "{{ ['Strobe color', 'Police', 'Christmas', 'RGB', 'Random Loop'] }}",
        ),
        (
            ["Police", "RGB", "Random Loop"],
            "{{ ['Police', 'RGB', 'Random Loop'] }}",
        ),
        (None, "{{ [] }}"),
        (None, "{{ '[]' }}"),
        (None, "{{ 124 }}"),
        (None, "{{ '124' }}"),
        (None, "{{ none }}"),
        (None, ""),
    ],
)
async def test_effect_list_template(
    hass, expected_effect_list, count, effect_list_template
):
    """Test the template for the effect list."""
    light_config = {
        "test_template_light": {
            **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
            "value_template": "{{ 1 == 1 }}",
            "set_effect": {
                "service": "test.automation",
                "data_template": {
                    "entity_id": "test.test_state",
                    "effect": "{{effect}}",
                },
            },
            "effect_template": "{{ None }}",
            "effect_list_template": effect_list_template,
        }
    }
    await async_setup_light(hass, count, light_config)
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("effect_list") == expected_effect_list


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "expected_effect,effect_template",
    [
        (None, "Disco"),
        (None, "None"),
        (None, "{{ None }}"),
        ("Police", "Police"),
        ("Strobe color", "{{ 'Strobe color' }}"),
    ],
)
async def test_effect_template(hass, expected_effect, count, effect_template):
    """Test the template for the effect."""
    light_config = {
        "test_template_light": {
            **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
            "value_template": "{{ 1 == 1 }}",
            "set_effect": {
                "service": "test.automation",
                "data_template": {
                    "entity_id": "test.test_state",
                    "effect": "{{effect}}",
                },
            },
            "effect_list_template": "{{ ['Strobe color', 'Police', 'Christmas', 'RGB', 'Random Loop'] }}",
            "effect_template": effect_template,
        }
    }
    await async_setup_light(hass, count, light_config)
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("effect") == expected_effect


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "expected_min_mireds,min_mireds_template",
    [
        (118, "{{118}}"),
        (153, "{{x - 12}}"),
        (153, "None"),
        (153, "{{ none }}"),
        (153, ""),
        (153, "{{ 'a' }}"),
    ],
)
async def test_min_mireds_template(
    hass, expected_min_mireds, count, min_mireds_template
):
    """Test the template for the min mireds."""
    light_config = {
        "test_template_light": {
            **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
            "value_template": "{{ 1 == 1 }}",
            "set_temperature": {
                "service": "light.turn_on",
                "data_template": {
                    "entity_id": "light.test_state",
                    "color_temp": "{{color_temp}}",
                },
            },
            "temperature_template": "{{200}}",
            "min_mireds_template": min_mireds_template,
        }
    }
    await async_setup_light(hass, count, light_config)
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("min_mireds") == expected_min_mireds


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "expected_max_mireds,max_mireds_template",
    [
        (488, "{{488}}"),
        (500, "{{x - 12}}"),
        (500, "None"),
        (500, "{{ none }}"),
        (500, ""),
        (500, "{{ 'a' }}"),
    ],
)
async def test_max_mireds_template(
    hass, expected_max_mireds, count, max_mireds_template
):
    """Test the template for the max mireds."""
    light_config = {
        "test_template_light": {
            **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
            "value_template": "{{ 1 == 1 }}",
            "set_temperature": {
                "service": "light.turn_on",
                "data_template": {
                    "entity_id": "light.test_state",
                    "color_temp": "{{color_temp}}",
                },
            },
            "temperature_template": "{{200}}",
            "max_mireds_template": max_mireds_template,
        }
    }
    await async_setup_light(hass, count, light_config)
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("max_mireds") == expected_max_mireds


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "expected_supports_transition,supports_transition_template",
    [
        (True, "{{true}}"),
        (True, "{{1 == 1}}"),
        (False, "{{false}}"),
        (False, "{{ none }}"),
        (False, ""),
        (False, "None"),
    ],
)
async def test_supports_transition_template(
    hass, expected_supports_transition, count, supports_transition_template
):
    """Test the template for the supports transition."""
    light_config = {
        "test_template_light": {
            "value_template": "{{ 1 == 1 }}",
            "turn_on": {"service": "light.turn_on", "entity_id": "light.test_state"},
            "turn_off": {"service": "light.turn_off", "entity_id": "light.test_state"},
            "set_temperature": {
                "service": "light.turn_on",
                "data_template": {
                    "entity_id": "light.test_state",
                    "color_temp": "{{color_temp}}",
                },
            },
            "supports_transition_template": supports_transition_template,
        }
    }
    await async_setup_light(hass, count, light_config)
    state = hass.states.get("light.test_template_light")

    expected_value = 1

    if expected_supports_transition is True:
        expected_value = 0

    assert state is not None
    assert (
        int(state.attributes.get("supported_features")) & LightEntityFeature.TRANSITION
    ) != expected_value


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "availability_template": "{{ is_state('availability_boolean.state', 'on') }}",
            }
        },
    ],
)
async def test_available_template_with_entities(hass, setup_light):
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


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "availability_template": "{{ x - 12 }}",
            }
        },
    ],
)
async def test_invalid_availability_template_keeps_component_available(
    hass, setup_light, caplog_setup_text
):
    """Test that an invalid availability keeps the device available."""
    assert hass.states.get("light.test_template_light").state != STATE_UNAVAILABLE
    assert ("UndefinedError: 'x' is undefined") in caplog_setup_text


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light_01": {
                **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                "unique_id": "not-so-unique-anymore",
            },
            "test_template_light_02": {
                **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                "unique_id": "not-so-unique-anymore",
            },
        },
    ],
)
async def test_unique_id(hass, setup_light):
    """Test unique_id option only creates one light per id."""
    assert len(hass.states.async_all("light")) == 1
