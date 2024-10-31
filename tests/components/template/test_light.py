"""The tests for the  Template light platform."""

from typing import Any

import pytest

from homeassistant.components import light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
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
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
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


OPTIMISTIC_LEGACY_COLOR_LIGHT_CONFIG = {
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


OPTIMISTIC_HS_COLOR_LIGHT_CONFIG = {
    **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
    "set_hs": {
        "service": "test.automation",
        "data_template": {
            "action": "set_hs",
            "caller": "{{ this.entity_id }}",
            "s": "{{s}}",
            "h": "{{h}}",
        },
    },
}


OPTIMISTIC_RGB_COLOR_LIGHT_CONFIG = {
    **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
    "set_rgb": {
        "service": "test.automation",
        "data_template": {
            "action": "set_rgb",
            "caller": "{{ this.entity_id }}",
            "r": "{{r}}",
            "g": "{{g}}",
            "b": "{{b}}",
        },
    },
}


OPTIMISTIC_RGBW_COLOR_LIGHT_CONFIG = {
    **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
    "set_rgbw": {
        "service": "test.automation",
        "data_template": {
            "action": "set_rgbw",
            "caller": "{{ this.entity_id }}",
            "r": "{{r}}",
            "g": "{{g}}",
            "b": "{{b}}",
            "w": "{{w}}",
        },
    },
}


OPTIMISTIC_RGBWW_COLOR_LIGHT_CONFIG = {
    **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
    "set_rgbww": {
        "service": "test.automation",
        "data_template": {
            "action": "set_rgbww",
            "caller": "{{ this.entity_id }}",
            "r": "{{r}}",
            "g": "{{g}}",
            "b": "{{b}}",
            "cw": "{{cw}}",
            "ww": "{{ww}}",
        },
    },
}


async def async_setup_light(
    hass: HomeAssistant, count: int, light_config: dict[str, Any]
) -> None:
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


async def async_setup_trigger_light(
    hass: HomeAssistant, count: int, light_config: dict[str, Any]
) -> None:
    """Do setup of triggered light integration."""
    config = {
        "template": {
            "unique_id": "listening-test-event",
            "trigger": {"platform": "event", "event_type": "test_event"},
            "light": light_config,
        }
    }

    with assert_setup_component(count, "template"):
        assert await async_setup_component(
            hass,
            "template",
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_attribute_template_test(
    hass: HomeAssistant,
    triggered: bool,
    config: dict[str, Any],
    attribute: str,
    template: str,
) -> None:
    """Do setup of attribute test."""
    name = "test_template_light"
    config[attribute] = template
    if triggered:
        config["name"] = name
        await async_setup_trigger_light(hass, 1, config)

        context = Context()
        hass.bus.async_fire("test_event", {"beer": 2}, context=context)
        await hass.async_block_till_done()

    else:
        config = {name: config}
        await async_setup_light(hass, 1, config)


@pytest.fixture
async def setup_light(
    hass: HomeAssistant, count: int, light_config: dict[str, Any]
) -> None:
    """Do setup of light integration."""
    await async_setup_light(hass, count, light_config)


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("supported_features", "supported_color_modes"),
    [(0, [ColorMode.BRIGHTNESS])],
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
    hass: HomeAssistant, supported_features, supported_color_modes, setup_light
) -> None:
    """Test template state with render error."""
    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count", [1])
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
async def test_template_state_text(hass: HomeAssistant, setup_light) -> None:
    """Test the state text of a template."""
    set_state = STATE_ON
    hass.states.async_set("light.test_state", set_state)
    await hass.async_block_till_done()
    state = hass.states.get("light.test_template_light")
    assert state.state == set_state
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0

    set_state = STATE_OFF
    hass.states.async_set("light.test_state", set_state)
    await hass.async_block_till_done()
    state = hass.states.get("light.test_template_light")
    assert state.state == set_state
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("value_template", "expected_state", "expected_color_mode"),
    [
        (
            "{{ 1 == 1 }}",
            STATE_ON,
            ColorMode.BRIGHTNESS,
        ),
        (
            "{{ 1 == 2 }}",
            STATE_OFF,
            None,
        ),
    ],
)
async def test_templatex_state_boolean(
    hass: HomeAssistant,
    expected_color_mode,
    expected_state,
    count,
    value_template,
) -> None:
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
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


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
async def test_template_syntax_error(hass: HomeAssistant, setup_light) -> None:
    """Test templating syntax error."""
    assert hass.states.async_all("light") == []


@pytest.mark.parametrize(
    ("light_config", "count"),
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
async def test_missing_key(hass: HomeAssistant, count, setup_light) -> None:
    """Test missing template."""
    if count:
        assert hass.states.async_all("light") != []
    else:
        assert hass.states.async_all("light") == []


@pytest.mark.parametrize("count", [1])
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
    hass: HomeAssistant, setup_light, calls: list[ServiceCall]
) -> None:
    """Test on action."""
    hass.states.async_set("light.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0

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
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
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
    hass: HomeAssistant, setup_light, calls: list[ServiceCall]
) -> None:
    """Test on action with transition."""
    hass.states.async_set("light.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == LightEntityFeature.TRANSITION

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_TRANSITION: 5},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["transition"] == 5

    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == LightEntityFeature.TRANSITION


@pytest.mark.parametrize("count", [1])
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
    hass: HomeAssistant,
    setup_light,
    calls: list[ServiceCall],
) -> None:
    """Test on action with optimistic state."""
    hass.states.async_set("light.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0

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
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0

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
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
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
    hass: HomeAssistant, setup_light, calls: list[ServiceCall]
) -> None:
    """Test off action."""
    hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0

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
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [(1)])
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
    hass: HomeAssistant, setup_light, calls: list[ServiceCall]
) -> None:
    """Test off action with transition."""
    hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == LightEntityFeature.TRANSITION

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_TRANSITION: 2},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["transition"] == 2
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == LightEntityFeature.TRANSITION


@pytest.mark.parametrize("count", [1])
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
    hass: HomeAssistant, setup_light, calls: list[ServiceCall]
) -> None:
    """Test off action with optimistic state."""
    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_template_light"},
        blocking=True,
    )

    assert len(calls) == 1
    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
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
    hass: HomeAssistant,
    setup_light,
    calls: list[ServiceCall],
) -> None:
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
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("triggered", "config", "attribute"),
    [
        (
            False,
            {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "value_template": "{{ 1 == 1 }}",
            },
            "level_template",
        ),
        (
            True,
            {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "state": "{{ trigger.event.data.beer == 2 }}",
            },
            "level",
        ),
    ],
)
@pytest.mark.parametrize(
    ("expected", "template", "expected_color_mode"),
    [
        (255, "{{255}}", ColorMode.BRIGHTNESS),
        (None, "{{256}}", ColorMode.BRIGHTNESS),
        (None, "{{ none }}", ColorMode.BRIGHTNESS),
        (None, "", ColorMode.BRIGHTNESS),
        (
            None,
            "{{ state_attr('light.nolight', 'brightness') }}",
            ColorMode.BRIGHTNESS,
        ),
        (None, "{{'one'}}", ColorMode.BRIGHTNESS),
    ],
)
async def test_level_template(
    hass: HomeAssistant,
    expected: Any,
    template: str,
    config: dict[str, Any],
    attribute: str,
    triggered: bool,
    expected_color_mode: ColorMode,
) -> None:
    """Test the template for the level."""
    await async_setup_attribute_template_test(
        hass, triggered, config, attribute, template
    )
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("brightness") == expected
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("triggered", "config", "attribute"),
    [
        (
            False,
            {
                **OPTIMISTIC_COLOR_TEMP_LIGHT_CONFIG,
                "value_template": "{{ 1 == 1 }}",
            },
            "temperature_template",
        ),
        (
            True,
            {
                **OPTIMISTIC_COLOR_TEMP_LIGHT_CONFIG,
                "state": "{{ trigger.event.data.beer == 2 }}",
            },
            "temperature",
        ),
    ],
)
@pytest.mark.parametrize(
    ("expected", "template", "expected_color_mode"),
    [
        (500, "{{500}}", ColorMode.COLOR_TEMP),
        (None, "{{501}}", ColorMode.COLOR_TEMP),
        (None, "None", ColorMode.COLOR_TEMP),
        (None, "{{ none }}", ColorMode.COLOR_TEMP),
        (None, "", ColorMode.COLOR_TEMP),
        (None, "{{ 'one' }}", ColorMode.COLOR_TEMP),
    ],
)
async def test_temperature_template(
    hass: HomeAssistant,
    expected: Any,
    template: str,
    config: dict[str, Any],
    attribute: str,
    triggered: bool,
    expected_color_mode: ColorMode,
) -> None:
    """Test the template for the temperature."""
    await async_setup_attribute_template_test(
        hass, triggered, config, attribute, template
    )
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("color_temp") == expected
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.COLOR_TEMP]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
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
    hass: HomeAssistant,
    setup_light,
    calls: list[ServiceCall],
) -> None:
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
    assert state.attributes["color_mode"] == ColorMode.COLOR_TEMP
    assert state.attributes["supported_color_modes"] == [ColorMode.COLOR_TEMP]
    assert state.attributes["supported_features"] == 0


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
async def test_friendly_name(hass: HomeAssistant, setup_light) -> None:
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
                "icon_template": (
                    "{% if states.light.test_state.state %}mdi:check{% endif %}"
                ),
            }
        },
    ],
)
async def test_icon_template(hass: HomeAssistant, setup_light) -> None:
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
                "entity_picture_template": (
                    "{% if states.light.test_state.state %}/local/light.png{% endif %}"
                ),
            }
        },
    ],
)
async def test_entity_picture_template(hass: HomeAssistant, setup_light) -> None:
    """Test entity_picture template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("entity_picture") == ""

    state = hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")

    assert state.attributes["entity_picture"] == "/local/light.png"


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_LEGACY_COLOR_LIGHT_CONFIG,
                "value_template": "{{1 == 1}}",
            }
        },
    ],
)
async def test_legacy_color_action_no_template(
    hass: HomeAssistant,
    setup_light,
    calls: list[ServiceCall],
) -> None:
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
    assert state.attributes["color_mode"] == ColorMode.HS
    assert state.attributes.get("hs_color") == (40, 50)
    assert state.attributes["supported_color_modes"] == [ColorMode.HS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
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
async def test_hs_color_action_no_template(
    hass: HomeAssistant,
    setup_light,
    calls: list[ServiceCall],
) -> None:
    """Test setting hs color with optimistic template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("hs_color") is None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_HS_COLOR: (40, 50)},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_hs"
    assert calls[-1].data["caller"] == "light.test_template_light"
    assert calls[-1].data["h"] == 40
    assert calls[-1].data["s"] == 50

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.HS
    assert state.attributes.get("hs_color") == (40, 50)
    assert state.attributes["supported_color_modes"] == [ColorMode.HS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_RGB_COLOR_LIGHT_CONFIG,
                "value_template": "{{1 == 1}}",
            }
        },
    ],
)
async def test_rgb_color_action_no_template(
    hass: HomeAssistant,
    setup_light,
    calls: list[ServiceCall],
) -> None:
    """Test setting rgb color with optimistic template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("rgb_color") is None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_RGB_COLOR: (160, 78, 192)},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_rgb"
    assert calls[-1].data["caller"] == "light.test_template_light"
    assert calls[-1].data["r"] == 160
    assert calls[-1].data["g"] == 78
    assert calls[-1].data["b"] == 192

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.RGB
    assert state.attributes.get("rgb_color") == (160, 78, 192)
    assert state.attributes["supported_color_modes"] == [ColorMode.RGB]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_RGBW_COLOR_LIGHT_CONFIG,
                "value_template": "{{1 == 1}}",
            }
        },
    ],
)
async def test_rgbw_color_action_no_template(
    hass: HomeAssistant,
    setup_light,
    calls: list[ServiceCall],
) -> None:
    """Test setting rgbw color with optimistic template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("rgbw_color") is None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_template_light",
            ATTR_RGBW_COLOR: (160, 78, 192, 25),
        },
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_rgbw"
    assert calls[-1].data["caller"] == "light.test_template_light"
    assert calls[-1].data["r"] == 160
    assert calls[-1].data["g"] == 78
    assert calls[-1].data["b"] == 192
    assert calls[-1].data["w"] == 25

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.RGBW
    assert state.attributes.get("rgbw_color") == (160, 78, 192, 25)
    assert state.attributes["supported_color_modes"] == [ColorMode.RGBW]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_RGBWW_COLOR_LIGHT_CONFIG,
                "value_template": "{{1 == 1}}",
            }
        },
    ],
)
async def test_rgbww_color_action_no_template(
    hass: HomeAssistant,
    setup_light,
    calls: list[ServiceCall],
) -> None:
    """Test setting rgbww color with optimistic template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("rgbww_color") is None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_template_light",
            ATTR_RGBWW_COLOR: (160, 78, 192, 25, 55),
        },
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_rgbww"
    assert calls[-1].data["caller"] == "light.test_template_light"
    assert calls[-1].data["r"] == 160
    assert calls[-1].data["g"] == 78
    assert calls[-1].data["b"] == 192
    assert calls[-1].data["cw"] == 25
    assert calls[-1].data["ww"] == 55

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.RGBWW
    assert state.attributes.get("rgbww_color") == (160, 78, 192, 25, 55)
    assert state.attributes["supported_color_modes"] == [ColorMode.RGBWW]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("triggered", "config", "attribute"),
    [
        (
            False,
            {
                **OPTIMISTIC_LEGACY_COLOR_LIGHT_CONFIG,
                "value_template": "{{ 1 == 1 }}",
            },
            "color_template",
        ),
        (
            True,
            {
                **OPTIMISTIC_LEGACY_COLOR_LIGHT_CONFIG,
                "state": "{{ trigger.event.data.beer == 2 }}",
            },
            "color",
        ),
    ],
)
@pytest.mark.parametrize(
    ("expected", "template", "expected_color_mode"),
    [
        ((360, 100), "{{(360, 100)}}", ColorMode.HS),
        ((359.9, 99.9), "{{(359.9, 99.9)}}", ColorMode.HS),
        (None, "{{(361, 100)}}", ColorMode.HS),
        (None, "{{(360, 101)}}", ColorMode.HS),
        (None, "[{{(360)}},{{null}}]", ColorMode.HS),
        (None, "", ColorMode.HS),
        (None, "{{ none }}", ColorMode.HS),
        (None, "{{('one','two')}}", ColorMode.HS),
    ],
)
async def test_legacy_color_template(
    hass: HomeAssistant,
    expected: Any,
    template: str,
    config: dict[str, Any],
    attribute: str,
    triggered: bool,
    expected_color_mode: ColorMode,
) -> None:
    """Test the template for the color."""
    await async_setup_attribute_template_test(
        hass, triggered, config, attribute, template
    )
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("hs_color") == expected
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.HS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("triggered", "config", "attribute"),
    [
        (
            False,
            {
                **OPTIMISTIC_HS_COLOR_LIGHT_CONFIG,
                "value_template": "{{ 1 == 1 }}",
            },
            "hs_template",
        ),
        (
            True,
            {
                **OPTIMISTIC_HS_COLOR_LIGHT_CONFIG,
                "state": "{{ trigger.event.data.beer == 2 }}",
            },
            "hs",
        ),
    ],
)
@pytest.mark.parametrize(
    ("expected", "template", "expected_color_mode"),
    [
        ((360, 100), "{{(360, 100)}}", ColorMode.HS),
        ((360, 100), "(360, 100)", ColorMode.HS),
        ((359.9, 99.9), "{{(359.9, 99.9)}}", ColorMode.HS),
        (None, "{{(361, 100)}}", ColorMode.HS),
        (None, "{{(360, 101)}}", ColorMode.HS),
        (None, "[{{(360)}},{{null}}]", ColorMode.HS),
        (None, "", ColorMode.HS),
        (None, "{{ none }}", ColorMode.HS),
        (None, "{{('one','two')}}", ColorMode.HS),
    ],
)
async def test_hs_template(
    hass: HomeAssistant,
    expected: Any,
    template: str,
    config: dict[str, Any],
    attribute: str,
    triggered: bool,
    expected_color_mode: ColorMode,
) -> None:
    """Test the template for the color."""
    await async_setup_attribute_template_test(
        hass, triggered, config, attribute, template
    )
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("hs_color") == expected
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.HS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("triggered", "config", "attribute"),
    [
        (
            False,
            {
                **OPTIMISTIC_RGB_COLOR_LIGHT_CONFIG,
                "value_template": "{{ 1 == 1 }}",
            },
            "rgb_template",
        ),
        (
            True,
            {
                **OPTIMISTIC_RGB_COLOR_LIGHT_CONFIG,
                "state": "{{ trigger.event.data.beer == 2 }}",
            },
            "rgb",
        ),
    ],
)
@pytest.mark.parametrize(
    ("expected", "template", "expected_color_mode"),
    [
        ((160, 78, 192), "{{(160, 78, 192)}}", ColorMode.RGB),
        ((160, 78, 192), "{{[160, 78, 192]}}", ColorMode.RGB),
        ((160, 78, 192), "(160, 78, 192)", ColorMode.RGB),
        ((159, 77, 191), "{{(159.9, 77.9, 191.9)}}", ColorMode.RGB),
        (None, "{{(256, 100, 100)}}", ColorMode.RGB),
        (None, "{{(100, 256, 100)}}", ColorMode.RGB),
        (None, "{{(100, 100, 256)}}", ColorMode.RGB),
        (None, "", ColorMode.RGB),
        (None, "{{ none }}", ColorMode.RGB),
        (None, "{{('one','two','tree')}}", ColorMode.RGB),
    ],
)
async def test_rgb_template(
    hass: HomeAssistant,
    expected: Any,
    template: str,
    config: dict[str, Any],
    attribute: str,
    triggered: bool,
    expected_color_mode: ColorMode,
) -> None:
    """Test the template for the color."""
    await async_setup_attribute_template_test(
        hass, triggered, config, attribute, template
    )
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("rgb_color") == expected
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.RGB]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("triggered", "config", "attribute"),
    [
        (
            False,
            {
                **OPTIMISTIC_RGBW_COLOR_LIGHT_CONFIG,
                "value_template": "{{ 1 == 1 }}",
            },
            "rgbw_template",
        ),
        (
            True,
            {
                **OPTIMISTIC_RGBW_COLOR_LIGHT_CONFIG,
                "state": "{{ trigger.event.data.beer == 2 }}",
            },
            "rgbw",
        ),
    ],
)
@pytest.mark.parametrize(
    ("expected", "template", "expected_color_mode"),
    [
        ((160, 78, 192, 25), "{{(160, 78, 192, 25)}}", ColorMode.RGBW),
        ((160, 78, 192, 25), "{{[160, 78, 192, 25]}}", ColorMode.RGBW),
        ((160, 78, 192, 25), "(160, 78, 192, 25)", ColorMode.RGBW),
        ((159, 77, 191, 24), "{{(159.9, 77.9, 191.9, 24.9)}}", ColorMode.RGBW),
        (None, "{{(256, 100, 100, 100)}}", ColorMode.RGBW),
        (None, "{{(100, 256, 100, 100)}}", ColorMode.RGBW),
        (None, "{{(100, 100, 256, 100)}}", ColorMode.RGBW),
        (None, "{{(100, 100, 100, 256)}}", ColorMode.RGBW),
        (None, "", ColorMode.RGBW),
        (None, "{{ none }}", ColorMode.RGBW),
        (None, "{{('one','two','tree','four')}}", ColorMode.RGBW),
    ],
)
async def test_rgbw_template(
    hass: HomeAssistant,
    expected: Any,
    template: str,
    config: dict[str, Any],
    attribute: str,
    triggered: bool,
    expected_color_mode: ColorMode,
) -> None:
    """Test the template for the color."""
    await async_setup_attribute_template_test(
        hass, triggered, config, attribute, template
    )
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("rgbw_color") == expected
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.RGBW]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("triggered", "config", "attribute"),
    [
        (
            False,
            {
                **OPTIMISTIC_RGBWW_COLOR_LIGHT_CONFIG,
                "value_template": "{{ 1 == 1 }}",
            },
            "rgbww_template",
        ),
        (
            True,
            {
                **OPTIMISTIC_RGBWW_COLOR_LIGHT_CONFIG,
                "state": "{{ trigger.event.data.beer == 2 }}",
            },
            "rgbww",
        ),
    ],
)
@pytest.mark.parametrize(
    ("expected", "template", "expected_color_mode"),
    [
        ((160, 78, 192, 25, 55), "{{(160, 78, 192, 25, 55)}}", ColorMode.RGBWW),
        ((160, 78, 192, 25, 55), "(160, 78, 192, 25, 55)", ColorMode.RGBWW),
        ((160, 78, 192, 25, 55), "{{[160, 78, 192, 25, 55]}}", ColorMode.RGBWW),
        (
            (159, 77, 191, 24, 54),
            "{{(159.9, 77.9, 191.9, 24.9, 54.9)}}",
            ColorMode.RGBWW,
        ),
        (None, "{{(256, 100, 100, 100, 100)}}", ColorMode.RGBWW),
        (None, "{{(100, 256, 100, 100, 100)}}", ColorMode.RGBWW),
        (None, "{{(100, 100, 256, 100, 100)}}", ColorMode.RGBWW),
        (None, "{{(100, 100, 100, 256, 100)}}", ColorMode.RGBWW),
        (None, "{{(100, 100, 100, 100, 256)}}", ColorMode.RGBWW),
        (None, "", ColorMode.RGBWW),
        (None, "{{ none }}", ColorMode.RGBWW),
        (None, "{{('one','two','tree','four','five')}}", ColorMode.RGBWW),
    ],
)
async def test_rgbww_template(
    hass: HomeAssistant,
    expected: Any,
    template: str,
    config: dict[str, Any],
    attribute: str,
    triggered: bool,
    expected_color_mode: ColorMode,
) -> None:
    """Test the template for the color."""
    await async_setup_attribute_template_test(
        hass, triggered, config, attribute, template
    )
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("rgbww_color") == expected
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.RGBWW]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("triggered", "config", "endswith", "expected_state"),
    [
        (
            False,
            {
                "value_template": "{{ 1 == 1 }}",
            },
            "_template",
            STATE_ON,
        ),
        (
            True,
            {
                "state": "{{ trigger.event.data.beer == 2 }}",
            },
            "",
            STATE_UNAVAILABLE,
        ),
    ],
)
@pytest.mark.parametrize(
    ("light_config", "field", "attribute", "expected_color_mode"),
    [
        (
            OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
            "level",
            "brightness",
            ColorMode.BRIGHTNESS,
        ),
        (
            OPTIMISTIC_COLOR_TEMP_LIGHT_CONFIG,
            "temperature",
            "color_temp",
            ColorMode.COLOR_TEMP,
        ),
        (OPTIMISTIC_LEGACY_COLOR_LIGHT_CONFIG, "color", "hs_color", ColorMode.HS),
        (OPTIMISTIC_RGB_COLOR_LIGHT_CONFIG, "rgb", "rgb_color", ColorMode.RGB),
        (OPTIMISTIC_RGBW_COLOR_LIGHT_CONFIG, "rgbw", "rgbw_color", ColorMode.RGBW),
        (OPTIMISTIC_RGBWW_COLOR_LIGHT_CONFIG, "rgbww", "rgbww_color", ColorMode.RGBWW),
    ],
)
async def test_invalid_color_template(
    hass: HomeAssistant,
    config: dict[str, Any],
    light_config: dict[str, Any],
    field: str,
    endswith: str,
    attribute: str,
    triggered: bool,
    expected_color_mode: ColorMode,
    expected_state: str,
) -> None:
    """Test the invalid templates for the color mode and state."""

    await async_setup_attribute_template_test(
        hass, triggered, {**config, **light_config}, f"{field}{endswith}", "{{x - 12}}"
    )
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get(attribute) is None
    assert state.state == expected_state
    assert state.attributes["supported_color_modes"] == [expected_color_mode]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "test_template_light": {
                **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                "value_template": "{{1 == 1}}",
                "set_hs": {
                    "service": "test.automation",
                    "data_template": {
                        "entity_id": "test.test_state",
                        "h": "{{h}}",
                        "s": "{{s}}",
                    },
                },
                "set_temperature": {
                    "service": "test.automation",
                    "data_template": {
                        "entity_id": "test.test_state",
                        "color_temp": "{{color_temp}}",
                    },
                },
                "set_rgb": {
                    "service": "test.automation",
                    "data_template": {
                        "entity_id": "test.test_state",
                        "r": "{{r}}",
                        "g": "{{g}}",
                        "b": "{{b}}",
                    },
                },
                "set_rgbw": {
                    "service": "test.automation",
                    "data_template": {
                        "entity_id": "test.test_state",
                        "r": "{{r}}",
                        "g": "{{g}}",
                        "b": "{{b}}",
                        "w": "{{w}}",
                    },
                },
                "set_rgbww": {
                    "service": "test.automation",
                    "data_template": {
                        "entity_id": "test.test_state",
                        "r": "{{r}}",
                        "g": "{{g}}",
                        "b": "{{b}}",
                        "cw": "{{cw}}",
                        "ww": "{{ww}}",
                    },
                },
            }
        },
    ],
)
async def test_all_colors_mode_no_template(
    hass: HomeAssistant, setup_light, calls: list[ServiceCall]
) -> None:
    """Test setting color and color temperature with optimistic template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("hs_color") is None

    # Optimistically set hs color, light should be in hs_color mode
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
    assert state.attributes["color_temp"] is None
    assert state.attributes["hs_color"] == (40, 50)
    assert state.attributes["supported_color_modes"] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
    ]
    assert state.attributes["supported_features"] == 0

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
    assert state.attributes["supported_color_modes"] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
    ]
    assert state.attributes["supported_features"] == 0

    # Optimistically set rgb color, light should be in rgb_color mode
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_RGB_COLOR: (160, 78, 192)},
        blocking=True,
    )

    assert len(calls) == 3
    assert calls[-1].data["r"] == 160
    assert calls[-1].data["g"] == 78
    assert calls[-1].data["b"] == 192

    state = hass.states.get("light.test_template_light")
    assert state.attributes["color_mode"] == ColorMode.RGB
    assert state.attributes["color_temp"] is None
    assert state.attributes["rgb_color"] == (160, 78, 192)
    assert state.attributes["supported_color_modes"] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
    ]
    assert state.attributes["supported_features"] == 0

    # Optimistically set rgbw color, light should be in rgb_color mode
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_template_light",
            ATTR_RGBW_COLOR: (160, 78, 192, 25),
        },
        blocking=True,
    )

    assert len(calls) == 4
    assert calls[-1].data["r"] == 160
    assert calls[-1].data["g"] == 78
    assert calls[-1].data["b"] == 192
    assert calls[-1].data["w"] == 25

    state = hass.states.get("light.test_template_light")
    assert state.attributes["color_mode"] == ColorMode.RGBW
    assert state.attributes["color_temp"] is None
    assert state.attributes["rgbw_color"] == (160, 78, 192, 25)
    assert state.attributes["supported_color_modes"] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
    ]
    assert state.attributes["supported_features"] == 0

    # Optimistically set rgbww color, light should be in rgb_color mode
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_template_light",
            ATTR_RGBWW_COLOR: (160, 78, 192, 25, 55),
        },
        blocking=True,
    )

    assert len(calls) == 5
    assert calls[-1].data["r"] == 160
    assert calls[-1].data["g"] == 78
    assert calls[-1].data["b"] == 192
    assert calls[-1].data["cw"] == 25
    assert calls[-1].data["ww"] == 55

    state = hass.states.get("light.test_template_light")
    assert state.attributes["color_mode"] == ColorMode.RGBWW
    assert state.attributes["color_temp"] is None
    assert state.attributes["rgbww_color"] == (160, 78, 192, 25, 55)
    assert state.attributes["supported_color_modes"] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
    ]
    assert state.attributes["supported_features"] == 0

    # Optimistically set hs color, light should again be in hs_color mode
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_HS_COLOR: (10, 20)},
        blocking=True,
    )

    assert len(calls) == 6
    assert calls[-1].data["h"] == 10
    assert calls[-1].data["s"] == 20

    state = hass.states.get("light.test_template_light")
    assert state.attributes["color_mode"] == ColorMode.HS
    assert state.attributes["color_temp"] is None
    assert state.attributes["hs_color"] == (10, 20)
    assert state.attributes["supported_color_modes"] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
    ]
    assert state.attributes["supported_features"] == 0

    # Optimistically set color temp, light should again be in color temp mode
    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_COLOR_TEMP: 234},
        blocking=True,
    )

    assert len(calls) == 7
    assert calls[-1].data["color_temp"] == 234

    state = hass.states.get("light.test_template_light")
    assert state.attributes["color_mode"] == ColorMode.COLOR_TEMP
    assert state.attributes["color_temp"] == 234
    assert "hs_color" in state.attributes  # Color temp represented as hs_color
    assert state.attributes["supported_color_modes"] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
    ]
    assert state.attributes["supported_features"] == 0


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
async def test_effect_action_valid_effect(
    hass: HomeAssistant, setup_light, calls: list[ServiceCall]
) -> None:
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
async def test_effect_action_invalid_effect(
    hass: HomeAssistant, setup_light, calls: list[ServiceCall]
) -> None:
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


@pytest.mark.parametrize(
    ("triggered", "config", "attribute"),
    [
        (
            False,
            {
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
            },
            "effect_list_template",
        ),
        (
            True,
            {
                **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                "state": "{{ trigger.event.data.beer == 2 }}",
                "set_effect": {
                    "service": "test.automation",
                    "data_template": {
                        "entity_id": "test.test_state",
                        "effect": "{{effect}}",
                    },
                },
                "effect": "{{ None }}",
            },
            "effect_list",
        ),
    ],
)
@pytest.mark.parametrize(
    ("expected", "template"),
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
    hass: HomeAssistant,
    expected: Any,
    template: str,
    config: dict[str, Any],
    attribute: str,
    triggered: bool,
) -> None:
    """Test the template for the effect list."""
    await async_setup_attribute_template_test(
        hass, triggered, config, attribute, template
    )
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("effect_list") == expected


@pytest.mark.parametrize(
    ("triggered", "config", "attribute"),
    [
        (
            False,
            {
                **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                "value_template": "{{ 1 == 1 }}",
                "set_effect": {
                    "service": "test.automation",
                    "data_template": {
                        "entity_id": "test.test_state",
                        "effect": "{{effect}}",
                    },
                },
                "effect_list_template": (
                    "{{ ['Strobe color', 'Police', 'Christmas', 'RGB', 'Random Loop'] }}"
                ),
            },
            "effect_template",
        ),
        (
            True,
            {
                **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                "state": "{{ trigger.event.data.beer == 2 }}",
                "set_effect": {
                    "service": "test.automation",
                    "data_template": {
                        "entity_id": "test.test_state",
                        "effect": "{{effect}}",
                    },
                },
                "effect_list": (
                    "{{ ['Strobe color', 'Police', 'Christmas', 'RGB', 'Random Loop'] }}"
                ),
            },
            "effect",
        ),
    ],
)
@pytest.mark.parametrize(
    ("expected", "template"),
    [
        (None, "Disco"),
        (None, "None"),
        (None, "{{ None }}"),
        ("Police", "Police"),
        ("Strobe color", "{{ 'Strobe color' }}"),
    ],
)
async def test_effect_template(
    hass: HomeAssistant,
    expected: Any,
    template: str,
    config: dict[str, Any],
    attribute: str,
    triggered: bool,
) -> None:
    """Test the template for the effect."""
    await async_setup_attribute_template_test(
        hass, triggered, config, attribute, template
    )
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("effect") == expected


@pytest.mark.parametrize(
    ("triggered", "config", "attribute"),
    [
        (
            False,
            {
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
            },
            "min_mireds_template",
        ),
        (
            True,
            {
                **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                "state": "{{ trigger.event.data.beer == 2 }}",
                "set_temperature": {
                    "service": "light.turn_on",
                    "data_template": {
                        "entity_id": "light.test_state",
                        "color_temp": "{{color_temp}}",
                    },
                },
                "temperature": "{{200}}",
            },
            "min_mireds",
        ),
    ],
)
@pytest.mark.parametrize(
    ("expected", "template"),
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
    hass: HomeAssistant,
    expected: Any,
    template: str,
    config: dict[str, Any],
    attribute: str,
    triggered: bool,
) -> None:
    """Test the template for the min mireds."""
    await async_setup_attribute_template_test(
        hass, triggered, config, attribute, template
    )
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("min_mireds") == expected


@pytest.mark.parametrize(
    ("triggered", "config", "attribute"),
    [
        (
            False,
            {
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
            },
            "max_mireds_template",
        ),
        (
            True,
            {
                **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                "state": "{{ trigger.event.data.beer == 2 }}",
                "set_temperature": {
                    "service": "light.turn_on",
                    "data_template": {
                        "entity_id": "light.test_state",
                        "color_temp": "{{color_temp}}",
                    },
                },
                "temperature": "{{200}}",
            },
            "max_mireds",
        ),
    ],
)
@pytest.mark.parametrize(
    ("expected", "template"),
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
    hass: HomeAssistant,
    expected: Any,
    template: str,
    config: dict[str, Any],
    attribute: str,
    triggered: bool,
) -> None:
    """Test the template for the max mireds."""
    await async_setup_attribute_template_test(
        hass, triggered, config, attribute, template
    )
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("max_mireds") == expected


@pytest.mark.parametrize(
    ("triggered", "config", "attribute"),
    [
        (
            False,
            {
                "value_template": "{{ 1 == 1 }}",
                "turn_on": {
                    "service": "light.turn_on",
                    "entity_id": "light.test_state",
                },
                "turn_off": {
                    "service": "light.turn_off",
                    "entity_id": "light.test_state",
                },
                "set_temperature": {
                    "service": "light.turn_on",
                    "data_template": {
                        "entity_id": "light.test_state",
                        "color_temp": "{{color_temp}}",
                    },
                },
            },
            "supports_transition_template",
        ),
        (
            True,
            {
                **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                "state": "{{ trigger.event.data.beer == 2 }}",
            },
            "supports_transition",
        ),
    ],
)
@pytest.mark.parametrize(
    ("expected", "template"),
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
    hass: HomeAssistant,
    expected: Any,
    template: str,
    config: dict[str, Any],
    attribute: str,
    triggered: bool,
) -> None:
    """Test the template for the supports transition."""
    await async_setup_attribute_template_test(
        hass, triggered, config, attribute, template
    )
    state = hass.states.get("light.test_template_light")

    expected_value = 1

    if expected is True:
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
                "availability_template": (
                    "{{ is_state('availability_boolean.state', 'on') }}"
                ),
            }
        },
    ],
)
async def test_available_template_with_entities(
    hass: HomeAssistant, setup_light
) -> None:
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
    hass: HomeAssistant, setup_light, caplog_setup_text
) -> None:
    """Test that an invalid availability keeps the device available."""
    assert hass.states.get("light.test_template_light").state != STATE_UNAVAILABLE
    assert "UndefinedError: 'x' is undefined" in caplog_setup_text


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
async def test_unique_id(hass: HomeAssistant, setup_light) -> None:
    """Test unique_id option only creates one light per id."""
    assert len(hass.states.async_all("light")) == 1


@pytest.mark.parametrize(("count", "domain"), [(2, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": [
                {"invalid": "config"},
                # Config after invalid should still be set up
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "lights": {
                        "hello": {
                            **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                            "friendly_name": "Hello Name",
                            "unique_id": "hello_name-id",
                            "value_template": "{{ trigger.event.data.beer == 2 }}",
                            "entity_picture_template": "{{ '/local/dogs.png' }}",
                            "icon_template": "{{ 'mdi:pirate' }}",
                        }
                    },
                    "light": [
                        {
                            **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                            "name": "via list",
                            "unique_id": "via_list-id",
                            "state": "{{ trigger.event.data.beer == 2 }}",
                            "picture": "{{ '/local/dogs2.png' if trigger.event.data.uno_mas is defined else '/local/dogs.png' }}",
                            "icon": "{{ 'mdi:pirate' }}",
                        },
                    ],
                },
                {
                    "trigger": [],
                    "lights": {
                        "bare_minimum": {**OPTIMISTIC_ON_OFF_LIGHT_CONFIG},
                    },
                },
            ],
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_trigger_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test trigger entity works."""
    await hass.async_block_till_done()
    state = hass.states.get("light.hello_name")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("light.via_list")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("light.bare_minimum")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 2}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("light.hello_name")
    assert state.state == STATE_ON
    assert state.attributes.get("icon") == "mdi:pirate"
    assert state.attributes.get("entity_picture") == "/local/dogs.png"
    assert state.context is context

    state = hass.states.get("light.via_list")
    assert state.state == STATE_ON
    assert state.attributes.get("icon") == "mdi:pirate"
    assert state.attributes.get("entity_picture") == "/local/dogs.png"
    assert state.context is context

    assert len(entity_registry.entities) == 2
    assert (
        entity_registry.entities["light.hello_name"].unique_id
        == "listening-test-event-hello_name-id"
    )
    assert (
        entity_registry.entities["light.via_list"].unique_id
        == "listening-test-event-via_list-id"
    )

    # Even if state itself didn't change, attributes might have changed
    hass.bus.async_fire("test_event", {"beer": 2, "uno_mas": "si"})
    await hass.async_block_till_done()
    state = hass.states.get("light.via_list")
    assert state.attributes.get("entity_picture") == "/local/dogs2.png"
    assert state.state == STATE_ON


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": [
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "light": [
                        {
                            **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                            "name": "optimistic",
                            "unique_id": "optimistic-id",
                            "picture": "{{ '/local/a.png' if trigger.event.data.beer == 2 else '/local/b.png' }}",
                        },
                        {
                            **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                            "name": "unavailable",
                            "unique_id": "unavailable-id",
                            "state": "{{ trigger.event.data.beer == 2 }}",
                            "availability": "{{ trigger.event.data.beer == 2 }}",
                        },
                    ],
                },
            ],
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_trigger_optimistic_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, calls: list[ServiceCall]
) -> None:
    """Test trigger entity works."""
    await hass.async_block_till_done()

    state = hass.states.get("light.optimistic")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("light.unavailable")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 2}, context=context)
    await hass.async_block_till_done()

    # Even if an event triggered, an optimistic switch should not change
    state = hass.states.get("light.optimistic")
    assert state is not None
    # Templated attributes should change
    assert state.attributes.get("entity_picture") == "/local/a.png"
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("light.unavailable")
    assert state.state == STATE_ON
    assert state.context is context

    assert len(entity_registry.entities) == 2
    assert (
        entity_registry.entities["light.optimistic"].unique_id
        == "listening-test-event-optimistic-id"
    )
    assert (
        entity_registry.entities["light.unavailable"].unique_id
        == "listening-test-event-unavailable-id"
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.optimistic"},
        blocking=True,
    )
    assert len(calls) == 1
    assert calls[-1].data["action"] == "turn_on"
    assert calls[-1].data["caller"] == "light.optimistic"

    state = hass.states.get("light.optimistic")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.optimistic"},
        blocking=True,
    )
    assert len(calls) == 2
    assert calls[-1].data["action"] == "turn_off"
    assert calls[-1].data["caller"] == "light.optimistic"

    state = hass.states.get("light.optimistic")
    assert state is not None
    assert state.state == STATE_OFF

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 1}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("light.optimistic")
    assert state is not None
    assert state.attributes.get("entity_picture") == "/local/b.png"
    assert state.state == STATE_OFF

    state = hass.states.get("light.unavailable")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "light_config",
    [
        {
            "turn_on": {
                "service": "test.automation",
                "data_template": {
                    "transition": "{{transition}}",
                },
            },
            "turn_off": {
                "service": "test.automation",
                "data_template": {
                    "transition": "{{transition}}",
                },
            },
            "set_level": {
                "service": "light.turn_on",
                "data_template": {
                    "entity_id": "light.test_state",
                    "brightness": "{{brightness}}",
                    "transition": "{{transition}}",
                },
            },
            "name": "test_template_light",
            "unique_id": "test_template_light",
            "state": "{{ trigger.event.data.beer == 2 }}",
            "supports_transition": "{{true}}",
        }
    ],
)
async def test_on_off_action_trigger_with_transition(
    hass: HomeAssistant, count: int, light_config: dict, calls: list[ServiceCall]
) -> None:
    """Test on action with transition."""
    await async_setup_trigger_light(hass, count, light_config)

    context = Context()
    hass.bus.async_fire("test_event", {"beer": 1}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == LightEntityFeature.TRANSITION

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_TRANSITION: 5},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data["transition"] == 5

    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == LightEntityFeature.TRANSITION

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_TRANSITION: 5},
        blocking=True,
    )

    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == LightEntityFeature.TRANSITION
