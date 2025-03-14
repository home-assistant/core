"""The tests for the  Template light platform."""

from typing import Any

import pytest

from homeassistant.components import light, template
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.components.template.light import rewrite_legacy_to_modern_conf
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component

from .conftest import ConfigurationStyle

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


TEST_STATE_TRIGGER = {
    "trigger": {"trigger": "state", "entity_id": "light.test_state"},
    "variables": {"triggering_entity": "{{ trigger.entity_id }}"},
    "action": [{"event": "action_event", "event_data": {"what": "triggering_entity"}}],
}


TEST_EVENT_TRIGGER = {
    "trigger": {"platform": "event", "event_type": "test_event"},
    "variables": {"type": "{{ trigger.event.data.type }}"},
    "action": [{"event": "action_event", "event_data": {"type": "{{ type }}"}}],
}


TEST_MISSING_KEY_CONFIG = {
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


TEST_ON_ACTION_WITH_TRANSITION_CONFIG = {
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
    "set_level": {
        "service": "light.turn_on",
        "data_template": {
            "entity_id": "light.test_state",
            "brightness": "{{brightness}}",
            "transition": "{{transition}}",
        },
    },
}


TEST_OFF_ACTION_WITH_TRANSITION_CONFIG = {
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
    "set_level": {
        "service": "light.turn_on",
        "data_template": {
            "entity_id": "light.test_state",
            "brightness": "{{brightness}}",
            "transition": "{{transition}}",
        },
    },
}


TEST_ALL_COLORS_NO_TEMPLATE_CONFIG = {
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


TEST_UNIQUE_ID_CONFIG = {
    **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
    "unique_id": "not-so-unique-anymore",
}


@pytest.mark.parametrize(
    ("old_attr", "new_attr", "attr_template"),
    [
        (
            "value_template",
            "state",
            "{{ 1 == 1 }}",
        ),
        (
            "rgb_template",
            "rgb",
            "{{ (255,255,255) }}",
        ),
        (
            "rgbw_template",
            "rgbw",
            "{{ (255,255,255,255) }}",
        ),
        (
            "rgbww_template",
            "rgbww",
            "{{ (255,255,255,255,255) }}",
        ),
        (
            "effect_list_template",
            "effect_list",
            "{{ ['a', 'b'] }}",
        ),
        (
            "effect_template",
            "effect",
            "{{ 'a' }}",
        ),
        (
            "level_template",
            "level",
            "{{ 255 }}",
        ),
        (
            "max_mireds_template",
            "max_mireds",
            "{{ 255 }}",
        ),
        (
            "min_mireds_template",
            "min_mireds",
            "{{ 255 }}",
        ),
        (
            "supports_transition_template",
            "supports_transition",
            "{{ True }}",
        ),
        (
            "temperature_template",
            "temperature",
            "{{ 255 }}",
        ),
        (
            "white_value_template",
            "white_value",
            "{{ 255 }}",
        ),
        (
            "hs_template",
            "hs",
            "{{ (255, 255) }}",
        ),
        (
            "color_template",
            "hs",
            "{{ (255, 255) }}",
        ),
    ],
)
async def test_legacy_to_modern_config(
    hass: HomeAssistant, old_attr: str, new_attr: str, attr_template: str
) -> None:
    """Test the conversion of legacy template to modern template."""
    config = {
        "foo": {
            "friendly_name": "foo bar",
            "unique_id": "foo-bar-light",
            "icon_template": "{{ 'mdi.abc' }}",
            "entity_picture_template": "{{ 'mypicture.jpg' }}",
            "availability_template": "{{ 1 == 1 }}",
            old_attr: attr_template,
            **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
        }
    }
    altered_configs = rewrite_legacy_to_modern_conf(hass, config)

    assert len(altered_configs) == 1

    assert [
        {
            "availability": Template("{{ 1 == 1 }}", hass),
            "icon": Template("{{ 'mdi.abc' }}", hass),
            "name": Template("foo bar", hass),
            "object_id": "foo",
            "picture": Template("{{ 'mypicture.jpg' }}", hass),
            "turn_off": {
                "data_template": {
                    "action": "turn_off",
                    "caller": "{{ this.entity_id }}",
                },
                "service": "test.automation",
            },
            "turn_on": {
                "data_template": {
                    "action": "turn_on",
                    "caller": "{{ this.entity_id }}",
                },
                "service": "test.automation",
            },
            "unique_id": "foo-bar-light",
            new_attr: Template(attr_template, hass),
        }
    ] == altered_configs


async def async_setup_legacy_format(
    hass: HomeAssistant, count: int, light_config: dict[str, Any]
) -> None:
    """Do setup of light integration via legacy format."""
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


async def async_setup_legacy_format_with_attribute(
    hass: HomeAssistant,
    count: int,
    attribute: str,
    attribute_template: str,
    extra_config: dict,
) -> None:
    """Do setup of a legacy light that has a single templated attribute."""
    extra = {attribute: attribute_template} if attribute and attribute_template else {}
    await async_setup_legacy_format(
        hass,
        count,
        {
            "test_template_light": {
                **extra_config,
                "value_template": "{{ 1 == 1 }}",
                **extra,
            }
        },
    )


async def async_setup_modern_format(
    hass: HomeAssistant, count: int, light_config: dict[str, Any]
) -> None:
    """Do setup of light integration via new format."""
    config = {"template": {"light": light_config}}

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_modern_format_with_attribute(
    hass: HomeAssistant,
    count: int,
    attribute: str,
    attribute_template: str,
    extra_config: dict,
) -> None:
    """Do setup of a legacy light that has a single templated attribute."""
    extra = {attribute: attribute_template} if attribute and attribute_template else {}
    await async_setup_modern_format(
        hass,
        count,
        {
            "name": "test_template_light",
            **extra_config,
            "state": "{{ 1 == 1 }}",
            **extra,
        },
    )


async def async_setup_trigger_format(
    hass: HomeAssistant, count: int, light_config: dict[str, Any]
) -> None:
    """Do setup of light integration via new format."""
    config = {
        "template": {
            **TEST_STATE_TRIGGER,
            "light": light_config,
        }
    }

    with assert_setup_component(count, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            config,
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()


async def async_setup_trigger_format_with_attribute(
    hass: HomeAssistant,
    count: int,
    attribute: str,
    attribute_template: str,
    extra_config: dict,
) -> None:
    """Do setup of a legacy light that has a single templated attribute."""
    extra = {attribute: attribute_template} if attribute and attribute_template else {}
    await async_setup_trigger_format(
        hass,
        count,
        {
            "name": "test_template_light",
            **extra_config,
            "state": "{{ 1 == 1 }}",
            **extra,
        },
    )


@pytest.fixture
async def setup_light(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    light_config: dict[str, Any],
) -> None:
    """Do setup of light integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(hass, count, light_config)
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(hass, count, light_config)
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(hass, count, light_config)


@pytest.fixture
async def setup_state_light(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
):
    """Do setup of light integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                "test_template_light": {
                    **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                    "value_template": state_template,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "name": "test_template_light",
                "state": state_template,
            },
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(
            hass,
            count,
            {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "name": "test_template_light",
                "state": state_template,
            },
        )


@pytest.fixture
async def setup_single_attribute_light(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    attribute: str,
    attribute_template: str,
    extra_config: dict,
) -> None:
    """Do setup of light integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format_with_attribute(
            hass, count, attribute, attribute_template, extra_config
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format_with_attribute(
            hass, count, attribute, attribute_template, extra_config
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format_with_attribute(
            hass, count, attribute, attribute_template, extra_config
        )


@pytest.fixture
async def setup_single_action_light(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    extra_config: dict,
) -> None:
    """Do setup of light integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format_with_attribute(
            hass, count, "", "", extra_config
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format_with_attribute(
            hass, count, "", "", extra_config
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format_with_attribute(
            hass, count, "", "", extra_config
        )


@pytest.fixture
async def setup_empty_action_light(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    action: str,
    extra_config: dict,
) -> None:
    """Do setup of light integration."""
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                "test_template_light": {
                    "turn_on": [],
                    "turn_off": [],
                    action: [],
                    **extra_config,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_new_format(
            hass,
            count,
            {
                "name": "test_template_light",
                "turn_on": [],
                "turn_off": [],
                action: [],
                **extra_config,
            },
        )


@pytest.fixture
async def setup_light_with_effects(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    effect_list_template: str,
    effect_template: str,
) -> None:
    """Do setup of light with effects."""
    common = {
        "set_effect": {
            "service": "test.automation",
            "data_template": {
                "action": "set_effect",
                "caller": "{{ this.entity_id }}",
                "entity_id": "test.test_state",
                "effect": "{{effect}}",
            },
        },
    }
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                "test_template_light": {
                    **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                    "value_template": "{{true}}",
                    **common,
                    "effect_list_template": effect_list_template,
                    "effect_template": effect_template,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                "name": "test_template_light",
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "state": "{{true}}",
                **common,
                "effect_list": effect_list_template,
                "effect": effect_template,
            },
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(
            hass,
            count,
            {
                "name": "test_template_light",
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "state": "{{true}}",
                **common,
                "effect_list": effect_list_template,
                "effect": effect_template,
            },
        )


@pytest.fixture
async def setup_light_with_mireds(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    attribute: str,
    attribute_template: str,
) -> None:
    """Do setup of light that uses mireds."""
    common = {
        "set_temperature": {
            "service": "light.turn_on",
            "data_template": {
                "entity_id": "light.test_state",
                "color_temp": "{{color_temp}}",
            },
        },
        attribute: attribute_template,
    }
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                "test_template_light": {
                    **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                    "value_template": "{{ 1 == 1 }}",
                    **common,
                    "temperature_template": "{{200}}",
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                "name": "test_template_light",
                **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                "state": "{{ 1 == 1 }}",
                **common,
                "temperature": "{{200}}",
            },
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(
            hass,
            count,
            {
                "name": "test_template_light",
                **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                "state": "{{ 1 == 1 }}",
                **common,
                "temperature": "{{200}}",
            },
        )


@pytest.fixture
async def setup_light_with_transition_template(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    transition_template: str,
) -> None:
    """Do setup of light that uses mireds."""
    common = {
        "set_effect": {
            "service": "test.automation",
            "data_template": {
                "entity_id": "test.test_state",
                "effect": "{{effect}}",
            },
        },
    }
    if style == ConfigurationStyle.LEGACY:
        await async_setup_legacy_format(
            hass,
            count,
            {
                "test_template_light": {
                    **OPTIMISTIC_COLOR_TEMP_LIGHT_CONFIG,
                    "value_template": "{{ 1 == 1 }}",
                    **common,
                    "effect_list_template": "{{ ['Disco', 'Police'] }}",
                    "effect_template": "{{ None }}",
                    "supports_transition_template": transition_template,
                }
            },
        )
    elif style == ConfigurationStyle.MODERN:
        await async_setup_modern_format(
            hass,
            count,
            {
                "name": "test_template_light",
                **OPTIMISTIC_COLOR_TEMP_LIGHT_CONFIG,
                "state": "{{ 1 == 1 }}",
                **common,
                "effect_list": "{{ ['Disco', 'Police'] }}",
                "effect": "{{ None }}",
                "supports_transition": transition_template,
            },
        )
    elif style == ConfigurationStyle.TRIGGER:
        await async_setup_trigger_format(
            hass,
            count,
            {
                "name": "test_template_light",
                **OPTIMISTIC_COLOR_TEMP_LIGHT_CONFIG,
                "state": "{{ 1 == 1 }}",
                **common,
                "effect_list": "{{ ['Disco', 'Police'] }}",
                "effect": "{{ None }}",
                "supports_transition": transition_template,
            },
        )


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("supported_features", "supported_color_modes"),
    [(0, [ColorMode.BRIGHTNESS])],
)
@pytest.mark.parametrize(
    ("style", "expected_state"),
    [
        (ConfigurationStyle.LEGACY, STATE_OFF),
        (ConfigurationStyle.MODERN, STATE_OFF),
        (ConfigurationStyle.TRIGGER, STATE_UNKNOWN),
    ],
)
@pytest.mark.parametrize("state_template", ["{{states.test['big.fat...']}}"])
async def test_template_state_invalid(
    hass: HomeAssistant,
    supported_features,
    supported_color_modes,
    expected_state,
    setup_state_light,
) -> None:
    """Test template state with render error."""
    state = hass.states.get("light.test_template_light")
    assert state.state == expected_state
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == supported_features


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style",
    [
        ConfigurationStyle.LEGACY,
        ConfigurationStyle.MODERN,
        ConfigurationStyle.TRIGGER,
    ],
)
@pytest.mark.parametrize("state_template", ["{{ states.light.test_state.state }}"])
async def test_template_state_text(hass: HomeAssistant, setup_state_light) -> None:
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
    "style",
    [
        ConfigurationStyle.LEGACY,
        ConfigurationStyle.MODERN,
        ConfigurationStyle.TRIGGER,
    ],
)
@pytest.mark.parametrize(
    ("state_template", "expected_state", "expected_color_mode"),
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
async def test_template_state_boolean(
    hass: HomeAssistant,
    expected_color_mode,
    expected_state,
    style,
    setup_state_light,
) -> None:
    """Test the setting of the state with boolean on."""
    if style == ConfigurationStyle.TRIGGER:
        hass.states.async_set("light.test_state", expected_state)
        await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == expected_state
    assert state.attributes.get("color_mode") == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [0])
@pytest.mark.parametrize(
    ("light_config", "style"),
    [
        (
            {
                "test_template_light": {
                    **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                    "value_template": "{%- if false -%}",
                }
            },
            ConfigurationStyle.LEGACY,
        ),
        (
            {
                "bad name here": {
                    **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                    "value_template": "{{ 1== 1}}",
                }
            },
            ConfigurationStyle.LEGACY,
        ),
        (
            {"test_template_light": "Invalid"},
            ConfigurationStyle.LEGACY,
        ),
        (
            {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "name": "test_template_light",
                "state": "{%- if false -%}",
            },
            ConfigurationStyle.MODERN,
        ),
        (
            {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "name": "test_template_light",
                "state": "{%- if false -%}",
            },
            ConfigurationStyle.TRIGGER,
        ),
    ],
)
async def test_template_config_errors(hass: HomeAssistant, setup_light) -> None:
    """Test template light configuration errors."""
    assert hass.states.async_all("light") == []


@pytest.mark.parametrize(
    ("light_config", "style", "count"),
    [
        (
            {"light_one": {"value_template": "{{ 1== 1}}", **TEST_MISSING_KEY_CONFIG}},
            ConfigurationStyle.LEGACY,
            0,
        ),
        (
            {"name": "light_one", "state": "{{ 1== 1}}", **TEST_MISSING_KEY_CONFIG},
            ConfigurationStyle.MODERN,
            0,
        ),
        (
            {"name": "light_one", "state": "{{ 1== 1}}", **TEST_MISSING_KEY_CONFIG},
            ConfigurationStyle.TRIGGER,
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
    "style",
    [
        ConfigurationStyle.LEGACY,
        ConfigurationStyle.MODERN,
        ConfigurationStyle.TRIGGER,
    ],
)
@pytest.mark.parametrize("state_template", ["{{ states.light.test_state.state }}"])
async def test_on_action(
    hass: HomeAssistant, setup_state_light, calls: list[ServiceCall]
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
    ("light_config", "style"),
    [
        (
            {
                "test_template_light": {
                    "value_template": "{{states.light.test_state.state}}",
                    **TEST_ON_ACTION_WITH_TRANSITION_CONFIG,
                    "supports_transition_template": "{{true}}",
                }
            },
            ConfigurationStyle.LEGACY,
        ),
        (
            {
                "name": "test_template_light",
                "state": "{{states.light.test_state.state}}",
                **TEST_ON_ACTION_WITH_TRANSITION_CONFIG,
                "supports_transition": "{{true}}",
            },
            ConfigurationStyle.MODERN,
        ),
        (
            {
                "name": "test_template_light",
                "state": "{{states.light.test_state.state}}",
                **TEST_ON_ACTION_WITH_TRANSITION_CONFIG,
                "supports_transition": "{{true}}",
            },
            ConfigurationStyle.TRIGGER,
        ),
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
    ("light_config", "style", "initial_state"),
    [
        (
            {
                "test_template_light": {
                    **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                }
            },
            ConfigurationStyle.LEGACY,
            STATE_OFF,
        ),
        (
            {
                "name": "test_template_light",
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
            },
            ConfigurationStyle.MODERN,
            STATE_OFF,
        ),
        (
            {
                "name": "test_template_light",
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
            },
            ConfigurationStyle.TRIGGER,
            STATE_UNKNOWN,
        ),
    ],
)
async def test_on_action_optimistic(
    hass: HomeAssistant,
    initial_state: str,
    setup_light,
    calls: list[ServiceCall],
) -> None:
    """Test on action with optimistic state."""
    hass.states.async_set("light.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")
    assert state.state == initial_state
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
    "style",
    [
        ConfigurationStyle.LEGACY,
        ConfigurationStyle.MODERN,
        ConfigurationStyle.TRIGGER,
    ],
)
@pytest.mark.parametrize("state_template", ["{{ states.light.test_state.state }}"])
async def test_off_action(
    hass: HomeAssistant, setup_state_light, calls: list[ServiceCall]
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
    ("light_config", "style"),
    [
        (
            {
                "test_template_light": {
                    "value_template": "{{states.light.test_state.state}}",
                    **TEST_OFF_ACTION_WITH_TRANSITION_CONFIG,
                    "supports_transition_template": "{{true}}",
                }
            },
            ConfigurationStyle.LEGACY,
        ),
        (
            {
                "name": "test_template_light",
                "state": "{{states.light.test_state.state}}",
                **TEST_OFF_ACTION_WITH_TRANSITION_CONFIG,
                "supports_transition": "{{true}}",
            },
            ConfigurationStyle.MODERN,
        ),
        (
            {
                "name": "test_template_light",
                "state": "{{states.light.test_state.state}}",
                **TEST_OFF_ACTION_WITH_TRANSITION_CONFIG,
                "supports_transition": "{{true}}",
            },
            ConfigurationStyle.TRIGGER,
        ),
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
    ("light_config", "style", "initial_state"),
    [
        (
            {
                "test_template_light": {
                    **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                }
            },
            ConfigurationStyle.LEGACY,
            STATE_OFF,
        ),
        (
            {
                "name": "test_template_light",
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
            },
            ConfigurationStyle.MODERN,
            STATE_OFF,
        ),
        (
            {
                "name": "test_template_light",
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
            },
            ConfigurationStyle.TRIGGER,
            STATE_UNKNOWN,
        ),
    ],
)
async def test_off_action_optimistic(
    hass: HomeAssistant, initial_state, setup_light, calls: list[ServiceCall]
) -> None:
    """Test off action with optimistic state."""
    state = hass.states.get("light.test_template_light")
    assert state.state == initial_state
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
    "style",
    [
        ConfigurationStyle.LEGACY,
        ConfigurationStyle.MODERN,
        ConfigurationStyle.TRIGGER,
    ],
)
@pytest.mark.parametrize("state_template", ["{{1 == 1}}"])
async def test_level_action_no_template(
    hass: HomeAssistant,
    setup_state_light,
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
    ("count", "extra_config"), [(1, OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG)]
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "level_template"),
        (ConfigurationStyle.MODERN, "level"),
        (ConfigurationStyle.TRIGGER, "level"),
    ],
)
@pytest.mark.parametrize(
    ("expected_level", "attribute_template", "expected_color_mode"),
    [
        (255, "{{255}}", ColorMode.BRIGHTNESS),
        (None, "{{256}}", ColorMode.BRIGHTNESS),
        (None, "{{x - 12}}", ColorMode.BRIGHTNESS),
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
    expected_level: Any,
    expected_color_mode: ColorMode,
    setup_single_attribute_light,
) -> None:
    """Test the template for the level."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("brightness") == expected_level
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, OPTIMISTIC_COLOR_TEMP_LIGHT_CONFIG)]
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "temperature_template"),
        (ConfigurationStyle.MODERN, "temperature"),
        (ConfigurationStyle.TRIGGER, "temperature"),
    ],
)
@pytest.mark.parametrize(
    ("expected_temp", "attribute_template", "expected_color_mode"),
    [
        (500, "{{500}}", ColorMode.COLOR_TEMP),
        (None, "{{501}}", ColorMode.COLOR_TEMP),
        (None, "{{x - 12}}", ColorMode.COLOR_TEMP),
        (None, "None", ColorMode.COLOR_TEMP),
        (None, "{{ none }}", ColorMode.COLOR_TEMP),
        (None, "", ColorMode.COLOR_TEMP),
        (None, "{{ 'one' }}", ColorMode.COLOR_TEMP),
    ],
)
async def test_temperature_template(
    hass: HomeAssistant,
    expected_temp: Any,
    expected_color_mode: ColorMode,
    setup_single_attribute_light,
) -> None:
    """Test the template for the temperature."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("color_temp") == expected_temp
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.COLOR_TEMP]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, OPTIMISTIC_COLOR_TEMP_LIGHT_CONFIG)]
)
@pytest.mark.parametrize(
    "style",
    [
        ConfigurationStyle.LEGACY,
        ConfigurationStyle.MODERN,
        ConfigurationStyle.TRIGGER,
    ],
)
async def test_temperature_action_no_template(
    hass: HomeAssistant,
    setup_single_action_light,
    calls: list[ServiceCall],
) -> None:
    """Test setting temperature with optimistic template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("color_template") is None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_COLOR_TEMP_KELVIN: 2898},
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
    ("light_config", "style", "entity_id"),
    [
        (
            {
                "test_template_light": {
                    **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                    "friendly_name": "Template light",
                    "value_template": "{{ 1 == 1 }}",
                }
            },
            ConfigurationStyle.LEGACY,
            "light.test_template_light",
        ),
        (
            {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "name": "Template light",
                "state": "{{ 1 == 1 }}",
            },
            ConfigurationStyle.MODERN,
            "light.template_light",
        ),
        (
            {
                **OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
                "name": "Template light",
                "state": "{{ 1 == 1 }}",
            },
            ConfigurationStyle.TRIGGER,
            "light.template_light",
        ),
    ],
)
async def test_friendly_name(hass: HomeAssistant, entity_id: str, setup_light) -> None:
    """Test the accessibility of the friendly_name attribute."""

    state = hass.states.get(entity_id)
    assert state is not None

    assert state.attributes.get("friendly_name") == "Template light"


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG)]
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "icon_template"),
        (ConfigurationStyle.MODERN, "icon"),
        (ConfigurationStyle.TRIGGER, "icon"),
    ],
)
@pytest.mark.parametrize(
    "attribute_template", ["{% if states.light.test_state.state %}mdi:check{% endif %}"]
)
async def test_icon_template(hass: HomeAssistant, setup_single_attribute_light) -> None:
    """Test icon template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("icon") == ""

    state = hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")

    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG)]
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "entity_picture_template"),
        (ConfigurationStyle.MODERN, "picture"),
        (ConfigurationStyle.TRIGGER, "picture"),
    ],
)
@pytest.mark.parametrize(
    "attribute_template",
    ["{% if states.light.test_state.state %}/local/light.png{% endif %}"],
)
async def test_entity_picture_template(
    hass: HomeAssistant, setup_single_attribute_light
) -> None:
    """Test entity_picture template."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("entity_picture") == ""

    state = hass.states.async_set("light.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_template_light")

    assert state.attributes["entity_picture"] == "/local/light.png"


@pytest.mark.parametrize(
    ("count", "extra_config"),
    [
        (1, OPTIMISTIC_LEGACY_COLOR_LIGHT_CONFIG),
    ],
)
@pytest.mark.parametrize(
    "style",
    [
        ConfigurationStyle.LEGACY,
    ],
)
async def test_legacy_color_action_no_template(
    hass: HomeAssistant,
    setup_single_action_light,
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


@pytest.mark.parametrize(
    ("count", "extra_config"),
    [
        (1, OPTIMISTIC_HS_COLOR_LIGHT_CONFIG),
    ],
)
@pytest.mark.parametrize(
    "style",
    [
        ConfigurationStyle.LEGACY,
        ConfigurationStyle.MODERN,
        ConfigurationStyle.TRIGGER,
    ],
)
async def test_hs_color_action_no_template(
    hass: HomeAssistant,
    setup_single_action_light,
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


@pytest.mark.parametrize(
    ("count", "extra_config"),
    [(1, OPTIMISTIC_RGB_COLOR_LIGHT_CONFIG)],
)
@pytest.mark.parametrize(
    "style",
    [
        ConfigurationStyle.LEGACY,
        ConfigurationStyle.MODERN,
        ConfigurationStyle.TRIGGER,
    ],
)
async def test_rgb_color_action_no_template(
    hass: HomeAssistant,
    setup_single_action_light,
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


@pytest.mark.parametrize(
    ("count", "extra_config"),
    [(1, OPTIMISTIC_RGBW_COLOR_LIGHT_CONFIG)],
)
@pytest.mark.parametrize(
    "style",
    [
        ConfigurationStyle.LEGACY,
        ConfigurationStyle.MODERN,
        ConfigurationStyle.TRIGGER,
    ],
)
async def test_rgbw_color_action_no_template(
    hass: HomeAssistant,
    setup_single_action_light,
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


@pytest.mark.parametrize(
    ("count", "extra_config"),
    [(1, OPTIMISTIC_RGBWW_COLOR_LIGHT_CONFIG)],
)
@pytest.mark.parametrize(
    "style",
    [
        ConfigurationStyle.LEGACY,
        ConfigurationStyle.MODERN,
        ConfigurationStyle.TRIGGER,
    ],
)
async def test_rgbww_color_action_no_template(
    hass: HomeAssistant,
    setup_single_action_light,
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


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("expected_hs", "color_template", "expected_color_mode"),
    [
        ((360, 100), "{{(360, 100)}}", ColorMode.HS),
        ((359.9, 99.9), "{{(359.9, 99.9)}}", ColorMode.HS),
        (None, "{{(361, 100)}}", ColorMode.HS),
        (None, "{{(360, 101)}}", ColorMode.HS),
        (None, "[{{(360)}},{{null}}]", ColorMode.HS),
        (None, "{{x - 12}}", ColorMode.HS),
        (None, "", ColorMode.HS),
        (None, "{{ none }}", ColorMode.HS),
        (None, "{{('one','two')}}", ColorMode.HS),
    ],
)
async def test_legacy_color_template(
    hass: HomeAssistant,
    expected_hs: tuple[float, float] | None,
    expected_color_mode: ColorMode,
    count: int,
    color_template: str,
) -> None:
    """Test the template for the color."""
    light_config = {
        "test_template_light": {
            **OPTIMISTIC_LEGACY_COLOR_LIGHT_CONFIG,
            "value_template": "{{ 1 == 1 }}",
            "color_template": color_template,
        }
    }
    await async_setup_legacy_format(hass, count, light_config)
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("hs_color") == expected_hs
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.HS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, OPTIMISTIC_HS_COLOR_LIGHT_CONFIG)]
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "hs_template"),
        (ConfigurationStyle.MODERN, "hs"),
        (ConfigurationStyle.TRIGGER, "hs"),
    ],
)
@pytest.mark.parametrize(
    ("expected_hs", "attribute_template", "expected_color_mode"),
    [
        ((360, 100), "{{(360, 100)}}", ColorMode.HS),
        ((360, 100), "(360, 100)", ColorMode.HS),
        ((359.9, 99.9), "{{(359.9, 99.9)}}", ColorMode.HS),
        (None, "{{(361, 100)}}", ColorMode.HS),
        (None, "{{(360, 101)}}", ColorMode.HS),
        (None, "[{{(360)}},{{null}}]", ColorMode.HS),
        (None, "{{x - 12}}", ColorMode.HS),
        (None, "", ColorMode.HS),
        (None, "{{ none }}", ColorMode.HS),
        (None, "{{('one','two')}}", ColorMode.HS),
    ],
)
async def test_hs_template(
    hass: HomeAssistant,
    expected_hs,
    expected_color_mode,
    setup_single_attribute_light,
) -> None:
    """Test the template for the color."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("hs_color") == expected_hs
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.HS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, OPTIMISTIC_RGB_COLOR_LIGHT_CONFIG)]
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "rgb_template"),
        (ConfigurationStyle.MODERN, "rgb"),
        (ConfigurationStyle.TRIGGER, "rgb"),
    ],
)
@pytest.mark.parametrize(
    ("expected_rgb", "attribute_template", "expected_color_mode"),
    [
        ((160, 78, 192), "{{(160, 78, 192)}}", ColorMode.RGB),
        ((160, 78, 192), "{{[160, 78, 192]}}", ColorMode.RGB),
        ((160, 78, 192), "(160, 78, 192)", ColorMode.RGB),
        ((159, 77, 191), "{{(159.9, 77.9, 191.9)}}", ColorMode.RGB),
        (None, "{{(256, 100, 100)}}", ColorMode.RGB),
        (None, "{{(100, 256, 100)}}", ColorMode.RGB),
        (None, "{{(100, 100, 256)}}", ColorMode.RGB),
        (None, "{{x - 12}}", ColorMode.RGB),
        (None, "", ColorMode.RGB),
        (None, "{{ none }}", ColorMode.RGB),
        (None, "{{('one','two','tree')}}", ColorMode.RGB),
    ],
)
async def test_rgb_template(
    hass: HomeAssistant,
    expected_rgb,
    expected_color_mode,
    setup_single_attribute_light,
) -> None:
    """Test the template for the color."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("rgb_color") == expected_rgb
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.RGB]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, OPTIMISTIC_RGBW_COLOR_LIGHT_CONFIG)]
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "rgbw_template"),
        (ConfigurationStyle.MODERN, "rgbw"),
        (ConfigurationStyle.TRIGGER, "rgbw"),
    ],
)
@pytest.mark.parametrize(
    ("expected_rgbw", "attribute_template", "expected_color_mode"),
    [
        ((160, 78, 192, 25), "{{(160, 78, 192, 25)}}", ColorMode.RGBW),
        ((160, 78, 192, 25), "{{[160, 78, 192, 25]}}", ColorMode.RGBW),
        ((160, 78, 192, 25), "(160, 78, 192, 25)", ColorMode.RGBW),
        ((159, 77, 191, 24), "{{(159.9, 77.9, 191.9, 24.9)}}", ColorMode.RGBW),
        (None, "{{(256, 100, 100, 100)}}", ColorMode.RGBW),
        (None, "{{(100, 256, 100, 100)}}", ColorMode.RGBW),
        (None, "{{(100, 100, 256, 100)}}", ColorMode.RGBW),
        (None, "{{(100, 100, 100, 256)}}", ColorMode.RGBW),
        (None, "{{x - 12}}", ColorMode.RGBW),
        (None, "", ColorMode.RGBW),
        (None, "{{ none }}", ColorMode.RGBW),
        (None, "{{('one','two','tree','four')}}", ColorMode.RGBW),
    ],
)
async def test_rgbw_template(
    hass: HomeAssistant,
    expected_rgbw,
    expected_color_mode,
    setup_single_attribute_light,
) -> None:
    """Test the template for the color."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("rgbw_color") == expected_rgbw
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.RGBW]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, OPTIMISTIC_RGBWW_COLOR_LIGHT_CONFIG)]
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "rgbww_template"),
        (ConfigurationStyle.MODERN, "rgbww"),
        (ConfigurationStyle.TRIGGER, "rgbww"),
    ],
)
@pytest.mark.parametrize(
    ("expected_rgbww", "attribute_template", "expected_color_mode"),
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
        (None, "{{x - 12}}", ColorMode.RGBWW),
        (None, "", ColorMode.RGBWW),
        (None, "{{ none }}", ColorMode.RGBWW),
        (None, "{{('one','two','tree','four','five')}}", ColorMode.RGBWW),
    ],
)
async def test_rgbww_template(
    hass: HomeAssistant,
    expected_rgbww,
    expected_color_mode,
    setup_single_attribute_light,
) -> None:
    """Test the template for the color."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes.get("rgbww_color") == expected_rgbww
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.RGBWW]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("light_config", "style"),
    [
        (
            {
                "test_template_light": {
                    **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                    "value_template": "{{1 == 1}}",
                    **TEST_ALL_COLORS_NO_TEMPLATE_CONFIG,
                }
            },
            ConfigurationStyle.LEGACY,
        ),
        (
            {
                "name": "test_template_light",
                **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                "state": "{{1 == 1}}",
                **TEST_ALL_COLORS_NO_TEMPLATE_CONFIG,
            },
            ConfigurationStyle.MODERN,
        ),
        (
            {
                "name": "test_template_light",
                **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                "state": "{{1 == 1}}",
                **TEST_ALL_COLORS_NO_TEMPLATE_CONFIG,
            },
            ConfigurationStyle.TRIGGER,
        ),
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
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_COLOR_TEMP_KELVIN: 8130},
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
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_COLOR_TEMP_KELVIN: 4273},
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
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("effect_list_template", "effect_template", "effect", "expected"),
    [
        ("{{ ['Disco', 'Police'] }}", "{{ 'Disco' }}", "Disco", "Disco"),
        ("{{ ['Disco', 'Police'] }}", "{{ 'None' }}", "RGB", None),
    ],
)
async def test_effect_action(
    hass: HomeAssistant,
    effect: str,
    expected: Any,
    setup_light_with_effects,
    calls: list[ServiceCall],
) -> None:
    """Test setting valid effect with template."""
    state = hass.states.get("light.test_template_light")
    assert state is not None

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light", ATTR_EFFECT: effect},
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[-1].data["action"] == "set_effect"
    assert calls[-1].data["caller"] == "light.test_template_light"
    assert calls[-1].data["effect"] == effect

    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("effect") == expected


@pytest.mark.parametrize(("count", "effect_template"), [(1, "{{ None }}")])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("expected_effect_list", "effect_list_template"),
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
    hass: HomeAssistant, expected_effect_list, setup_light_with_effects
) -> None:
    """Test the template for the effect list."""
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("effect_list") == expected_effect_list


@pytest.mark.parametrize(
    ("count", "effect_list_template"),
    [(1, "{{ ['Strobe color', 'Police', 'Christmas', 'RGB', 'Random Loop'] }}")],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("expected_effect", "effect_template"),
    [
        (None, "Disco"),
        (None, "None"),
        (None, "{{ None }}"),
        ("Police", "Police"),
        ("Strobe color", "{{ 'Strobe color' }}"),
    ],
)
async def test_effect_template(
    hass: HomeAssistant, expected_effect, setup_light_with_effects
) -> None:
    """Test the template for the effect."""
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("effect") == expected_effect


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "min_mireds_template"),
        (ConfigurationStyle.MODERN, "min_mireds"),
        (ConfigurationStyle.TRIGGER, "min_mireds"),
    ],
)
@pytest.mark.parametrize(
    ("expected_min_mireds", "attribute_template"),
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
    hass: HomeAssistant, expected_min_mireds, setup_light_with_mireds
) -> None:
    """Test the template for the min mireds."""
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("min_mireds") == expected_min_mireds


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "max_mireds_template"),
        (ConfigurationStyle.MODERN, "max_mireds"),
        (ConfigurationStyle.TRIGGER, "max_mireds"),
    ],
)
@pytest.mark.parametrize(
    ("expected_max_mireds", "attribute_template"),
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
    hass: HomeAssistant, expected_max_mireds, setup_light_with_mireds
) -> None:
    """Test the template for the max mireds."""
    state = hass.states.get("light.test_template_light")
    assert state is not None
    assert state.attributes.get("max_mireds") == expected_max_mireds


@pytest.mark.parametrize(
    ("count", "extra_config"), [(1, OPTIMISTIC_COLOR_TEMP_LIGHT_CONFIG)]
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "supports_transition_template"),
        (ConfigurationStyle.MODERN, "supports_transition"),
        (ConfigurationStyle.TRIGGER, "supports_transition"),
    ],
)
@pytest.mark.parametrize(
    ("expected_supports_transition", "attribute_template"),
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
    hass: HomeAssistant, expected_supports_transition, setup_single_attribute_light
) -> None:
    """Test the template for the supports transition."""
    state = hass.states.get("light.test_template_light")

    expected_value = 1

    if expected_supports_transition is True:
        expected_value = 0

    assert state is not None
    assert (
        int(state.attributes.get("supported_features")) & LightEntityFeature.TRANSITION
    ) != expected_value


@pytest.mark.parametrize(
    ("count", "transition_template"), [(1, "{{ states('sensor.test') }}")]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_supports_transition_template_updates(
    hass: HomeAssistant, setup_light_with_transition_template
) -> None:
    """Test the template for the supports transition dynamically."""
    state = hass.states.get("light.test_template_light")
    assert state is not None

    hass.states.async_set("sensor.test", 0)
    await hass.async_block_till_done()
    state = hass.states.get("light.test_template_light")
    supported_features = state.attributes.get("supported_features")
    assert supported_features == LightEntityFeature.EFFECT

    hass.states.async_set("sensor.test", 1)
    await hass.async_block_till_done()
    state = hass.states.get("light.test_template_light")
    supported_features = state.attributes.get("supported_features")
    assert (
        supported_features == LightEntityFeature.TRANSITION | LightEntityFeature.EFFECT
    )

    hass.states.async_set("sensor.test", 0)
    await hass.async_block_till_done()
    state = hass.states.get("light.test_template_light")
    supported_features = state.attributes.get("supported_features")
    assert supported_features == LightEntityFeature.EFFECT


@pytest.mark.parametrize(
    ("count", "extra_config", "attribute_template"),
    [
        (
            1,
            OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
            "{{ is_state('availability_boolean.state', 'on') }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "availability_template"),
        (ConfigurationStyle.MODERN, "availability"),
        (ConfigurationStyle.TRIGGER, "availability"),
    ],
)
async def test_available_template_with_entities(
    hass: HomeAssistant, setup_single_attribute_light
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


@pytest.mark.parametrize(
    ("count", "extra_config", "attribute_template"),
    [
        (
            1,
            OPTIMISTIC_BRIGHTNESS_LIGHT_CONFIG,
            "{{ x - 12 }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "availability_template"),
        (ConfigurationStyle.MODERN, "availability"),
        (ConfigurationStyle.TRIGGER, "availability"),
    ],
)
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, setup_single_attribute_light, caplog_setup_text
) -> None:
    """Test that an invalid availability keeps the device available."""
    assert hass.states.get("light.test_template_light").state != STATE_UNAVAILABLE
    assert "UndefinedError: 'x' is undefined" in caplog_setup_text


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("light_config", "style"),
    [
        (
            {
                "test_template_light_01": TEST_UNIQUE_ID_CONFIG,
                "test_template_light_02": TEST_UNIQUE_ID_CONFIG,
            },
            ConfigurationStyle.LEGACY,
        ),
        (
            [
                {
                    "name": "test_template_light_01",
                    **TEST_UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_light_02",
                    **TEST_UNIQUE_ID_CONFIG,
                },
            ],
            ConfigurationStyle.MODERN,
        ),
        (
            [
                {
                    "name": "test_template_light_01",
                    **TEST_UNIQUE_ID_CONFIG,
                },
                {
                    "name": "test_template_light_02",
                    **TEST_UNIQUE_ID_CONFIG,
                },
            ],
            ConfigurationStyle.TRIGGER,
        ),
    ],
)
async def test_unique_id(hass: HomeAssistant, setup_light) -> None:
    """Test unique_id option only creates one light per id."""
    assert len(hass.states.async_all("light")) == 1


async def test_nested_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test unique_id option creates one light per nested id."""

    with assert_setup_component(1, template.DOMAIN):
        assert await async_setup_component(
            hass,
            template.DOMAIN,
            {
                "template": {
                    "unique_id": "x",
                    "light": [
                        {
                            "name": "test_a",
                            **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                            "unique_id": "a",
                        },
                        {
                            "name": "test_b",
                            **OPTIMISTIC_ON_OFF_LIGHT_CONFIG,
                            "unique_id": "b",
                        },
                    ],
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all("light")) == 2

    entry = entity_registry.async_get("light.test_a")
    assert entry
    assert entry.unique_id == "x-a"

    entry = entity_registry.async_get("light.test_b")
    assert entry
    assert entry.unique_id == "x-b"


@pytest.mark.parametrize(("count", "extra_config"), [(1, {})])
@pytest.mark.parametrize(
    "style",
    [
        ConfigurationStyle.LEGACY,
        ConfigurationStyle.MODERN,
    ],
)
@pytest.mark.parametrize(
    ("action", "color_mode"),
    [
        ("set_level", ColorMode.BRIGHTNESS),
        ("set_temperature", ColorMode.COLOR_TEMP),
        ("set_hs", ColorMode.HS),
        ("set_rgb", ColorMode.RGB),
        ("set_rgbw", ColorMode.RGBW),
        ("set_rgbww", ColorMode.RGBWW),
    ],
)
async def test_empty_color_mode_action_config(
    hass: HomeAssistant,
    color_mode: ColorMode,
    setup_empty_action_light,
) -> None:
    """Test empty actions for color mode actions."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes["supported_color_modes"] == [color_mode]

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_template_light"},
        blocking=True,
    )

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_ON

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_template_light"},
        blocking=True,
    )

    state = hass.states.get("light.test_template_light")
    assert state.state == STATE_OFF


@pytest.mark.parametrize(("count"), [1])
@pytest.mark.parametrize(
    ("style", "extra_config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "effect_list_template": "{{ ['a'] }}",
                "effect_template": "{{ 'a' }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "effect_list": "{{ ['a'] }}",
                "effect": "{{ 'a' }}",
            },
        ),
    ],
)
@pytest.mark.parametrize("action", ["set_effect"])
async def test_effect_with_empty_action(
    hass: HomeAssistant,
    setup_empty_action_light,
) -> None:
    """Test empty set_effect action."""
    state = hass.states.get("light.test_template_light")
    assert state.attributes["supported_features"] == LightEntityFeature.EFFECT
