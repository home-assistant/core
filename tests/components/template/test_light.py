"""The tests for the  Template light platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

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
from homeassistant.helpers.typing import ConfigType

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    assert_action,
    async_get_flow_preview_state,
    async_setup_legacy_platforms,
    async_trigger,
    make_test_action,
    make_test_trigger,
    setup_and_test_nested_unique_id,
    setup_and_test_unique_id,
    setup_entity,
)

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

TEST_STATE_ENTITY_ID = "light.test_state"
TEST_AVAILABILITY_ENTITY = "binary_sensor.availability"

TEST_LIGHT = TemplatePlatformSetup(
    light.DOMAIN,
    "lights",
    "test_light",
    make_test_trigger(
        TEST_STATE_ENTITY_ID,
        TEST_AVAILABILITY_ENTITY,
    ),
)

ON_ACTION = make_test_action("turn_on")
OFF_ACTION = make_test_action("turn_off")
ON_OFF_ACTIONS = {
    **ON_ACTION,
    **OFF_ACTION,
}


BRIGHTNESS_DATA = {"brightness": "{{ brightness }}"}
SET_LEVEL_ACTION = make_test_action("set_level", BRIGHTNESS_DATA)
ON_OFF_SET_LEVEL_ACTIONS = {
    **ON_OFF_ACTIONS,
    **SET_LEVEL_ACTION,
}

COLOR_TEMP_ACTION = make_test_action(
    "set_temperature",
    {
        "color_temp": "{{color_temp}}",
        "color_temp_kelvin": "{{color_temp_kelvin}}",
    },
)
ON_OFF_COLOR_TEMP_ACTIONS = {
    **ON_OFF_ACTIONS,
    **COLOR_TEMP_ACTION,
}


ON_OFF_LEGACY_COLOR_ACTIONS = {
    **ON_OFF_ACTIONS,
    **make_test_action(
        "set_color",
        {"s": "{{ s }}", "h": "{{ h }}"},
    ),
}

HS_ACTION = make_test_action(
    "set_hs",
    {"s": "{{ s }}", "h": "{{ h }}"},
)
ON_OFF_HS_ACTIONS = {
    **ON_OFF_ACTIONS,
    **HS_ACTION,
}

RGB_ACTION = make_test_action(
    "set_rgb",
    {"r": "{{ r }}", "g": "{{ g }}", "b": "{{ b }}"},
)
ON_OFF_RGB_ACTIONS = {
    **ON_OFF_ACTIONS,
    **RGB_ACTION,
}

RGBW_ACTION = make_test_action(
    "set_rgbw",
    {"r": "{{ r }}", "g": "{{ g }}", "b": "{{ b }}", "w": "{{ w }}"},
)
ON_OFF_RGBW_ACTIONS = {
    **ON_OFF_ACTIONS,
    **RGBW_ACTION,
}

RGBWW_ACTION = make_test_action(
    "set_rgbww",
    {
        "r": "{{ r }}",
        "g": "{{ g }}",
        "b": "{{ b }}",
        "cw": "{{ cw }}",
        "ww": "{{ ww }}",
    },
)
ON_OFF_RGBWW_ACTIONS = {
    **ON_OFF_ACTIONS,
    **RGBWW_ACTION,
}

SET_EFFECT_ACTION = make_test_action("set_effect", {"effect": "{{ effect }}"})

TRANSITION_DATA = {"transition": "{{ transition }}"}
OFF_TRANSITION_ACTION = make_test_action("turn_off", TRANSITION_DATA)
ON_ACTION_WITH_TRANSITION = {
    **make_test_action("turn_on", TRANSITION_DATA),
    **OFF_ACTION,
    **make_test_action("set_level", {**BRIGHTNESS_DATA, **TRANSITION_DATA}),
}


OFF_ACTION_WITH_TRANSITION = {
    **ON_ACTION,
    **make_test_action("turn_off", TRANSITION_DATA),
    **make_test_action("set_level", {**BRIGHTNESS_DATA, **TRANSITION_DATA}),
}


ALL_COLOR_ACTIONS = {
    **HS_ACTION,
    **COLOR_TEMP_ACTION,
    **RGB_ACTION,
    **RGBW_ACTION,
    **RGBWW_ACTION,
}


async def _call_and_assert_action(
    hass: HomeAssistant,
    calls: list[ServiceCall],
    service: str,
    service_data: ConfigType | None = None,
    expected_data: ConfigType | None = None,
    expected_action: str | None = None,
) -> None:
    """Call a service and validate that it was called properly.

    The service is validated when expected_action is omitted.
    """
    if expected_action is None:
        expected_action = service
    current = len(calls)
    await hass.services.async_call(
        light.DOMAIN,
        service,
        {**(service_data or {}), ATTR_ENTITY_ID: TEST_LIGHT.entity_id},
        blocking=True,
    )
    assert_action(
        TEST_LIGHT, calls, current + 1, expected_action, **(expected_data or {})
    )


@pytest.fixture
async def setup_light(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: dict[str, Any],
) -> None:
    """Do setup of light integration."""
    await setup_entity(hass, TEST_LIGHT, style, count, config)


@pytest.fixture
async def setup_state_light(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
    extra_config: ConfigType,
):
    """Do setup of light integration."""
    await setup_entity(
        hass,
        TEST_LIGHT,
        style,
        count,
        ON_OFF_SET_LEVEL_ACTIONS,
        state_template,
        extra_config,
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
    await setup_entity(
        hass,
        TEST_LIGHT,
        style,
        count,
        {attribute: attribute_template} if attribute and attribute_template else {},
        "{{ 1 == 1 }}",
        extra_config,
    )


@pytest.fixture
async def setup_single_action_light(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    extra_config: dict,
) -> None:
    """Do setup of light integration."""
    await setup_entity(
        hass,
        TEST_LIGHT,
        style,
        count,
        extra_config,
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
    await setup_entity(
        hass,
        TEST_LIGHT,
        style,
        count,
        {"turn_on": [], "turn_off": [], action: []},
        extra_config=extra_config,
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

    await setup_entity(
        hass,
        TEST_LIGHT,
        style,
        count,
        {
            **SET_EFFECT_ACTION,
            **(
                {
                    "effect_list_template": effect_list_template,
                    "effect_template": effect_template,
                }
                if style == ConfigurationStyle.LEGACY
                else {
                    "effect_list": effect_list_template,
                    "effect": effect_template,
                }
            ),
        },
        "{{ true }}",
        ON_OFF_ACTIONS,
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
    await setup_entity(
        hass,
        TEST_LIGHT,
        style,
        count,
        {
            attribute: attribute_template,
            **make_test_action("set_temperature", {"color_temp": "{{ color_temp }}"}),
            **(
                {"temperature_template": "{{ 200 }}"}
                if style == ConfigurationStyle.LEGACY
                else {"temperature": "{{ 200 }}"}
            ),
        },
        "{{ 1==1 }}",
        ON_OFF_ACTIONS,
    )


@pytest.fixture
async def setup_light_with_transition_template(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    transition_template: str,
) -> None:
    """Do setup of light that uses mireds."""
    await setup_entity(
        hass,
        TEST_LIGHT,
        style,
        count,
        {
            **SET_EFFECT_ACTION,
            **(
                {
                    "effect_list_template": "{{ ['Disco', 'Police'] }}",
                    "effect_template": "{{ None }}",
                    "supports_transition_template": transition_template,
                }
                if style == ConfigurationStyle.LEGACY
                else {
                    "effect_list": "{{ ['Disco', 'Police'] }}",
                    "effect": "{{ None }}",
                    "supports_transition": transition_template,
                }
            ),
        },
        "{{ 1==1 }}",
        ON_OFF_ACTIONS,
    )


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{states.test['big.fat...']}}", {})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_light")
async def test_template_state_invalid(hass: HomeAssistant) -> None:
    """Test template state with render error."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, None)

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ states.light.test_state.state }}", {})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_light")
async def test_template_state_text(hass: HomeAssistant) -> None:
    """Test the state text of a template."""
    set_state = STATE_ON
    await async_trigger(hass, TEST_STATE_ENTITY_ID, set_state)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == set_state
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0

    set_state = STATE_OFF
    await async_trigger(hass, TEST_STATE_ENTITY_ID, set_state)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == set_state
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(("count", "extra_config"), [(1, {})])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
@pytest.mark.usefixtures("setup_state_light")
async def test_template_state_boolean(
    hass: HomeAssistant,
    expected_color_mode: ColorMode | None,
    expected_state: str,
) -> None:
    """Test the setting of the state with boolean on."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, expected_state)

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == expected_state
    assert state.attributes.get("color_mode") == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


async def test_legacy_template_config_errors(hass: HomeAssistant) -> None:
    """Test legacy template light configuration errors."""
    await async_setup_legacy_platforms(
        hass,
        light.DOMAIN,
        "bad name here",
        0,
        {
            **ON_OFF_SET_LEVEL_ACTIONS,
            "value_template": "{{ 1== 1}}",
        },
    )
    assert hass.states.async_all("light") == []


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"), [(0, "{%- if false -%}", {})]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_light")
async def test_template_config_errors(hass: HomeAssistant) -> None:
    """Test template light configuration errors."""
    assert hass.states.async_all("light") == []


@pytest.mark.parametrize(
    ("count", "config"),
    [(0, {**ON_ACTION, **SET_LEVEL_ACTION})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_light")
async def test_missing_key(hass: HomeAssistant) -> None:
    """Test missing template."""
    assert hass.states.async_all("light") == []


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ states.light.test_state.state }}", {})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_light")
async def test_on_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test on action."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0

    await _call_and_assert_action(hass, calls, SERVICE_TURN_ON)

    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("config", "style"),
    [
        (
            {
                "value_template": "{{states.light.test_state.state}}",
                **ON_ACTION_WITH_TRANSITION,
                "supports_transition_template": "{{true}}",
            },
            ConfigurationStyle.LEGACY,
        ),
        (
            {
                "state": "{{states.light.test_state.state}}",
                **ON_ACTION_WITH_TRANSITION,
                "supports_transition": "{{true}}",
            },
            ConfigurationStyle.MODERN,
        ),
        (
            {
                "state": "{{states.light.test_state.state}}",
                **ON_ACTION_WITH_TRANSITION,
                "supports_transition": "{{true}}",
            },
            ConfigurationStyle.TRIGGER,
        ),
    ],
)
@pytest.mark.usefixtures("setup_light")
async def test_on_action_with_transition(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test on action with transition."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == LightEntityFeature.TRANSITION

    await _call_and_assert_action(
        hass, calls, SERVICE_TURN_ON, {ATTR_TRANSITION: 5}, {ATTR_TRANSITION: 5}
    )

    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == LightEntityFeature.TRANSITION


@pytest.mark.parametrize(("count", "config"), [(1, ON_OFF_SET_LEVEL_ACTIONS)])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_light")
async def test_on_action_optimistic(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test on action with optimistic state."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_UNKNOWN
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0

    await _call_and_assert_action(hass, calls, SERVICE_TURN_ON)

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {ATTR_BRIGHTNESS: 100},
        {ATTR_BRIGHTNESS: 100},
        "set_level",
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ states.light.test_state.state }}", {})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_light")
async def test_off_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test off action."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0

    await _call_and_assert_action(hass, calls, SERVICE_TURN_OFF)

    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [(1)])
@pytest.mark.parametrize(
    ("config", "style"),
    [
        (
            {
                "value_template": "{{states.light.test_state.state}}",
                **OFF_ACTION_WITH_TRANSITION,
                "supports_transition_template": "{{true}}",
            },
            ConfigurationStyle.LEGACY,
        ),
        (
            {
                "state": "{{states.light.test_state.state}}",
                **OFF_ACTION_WITH_TRANSITION,
                "supports_transition": "{{true}}",
            },
            ConfigurationStyle.MODERN,
        ),
        (
            {
                "state": "{{states.light.test_state.state}}",
                **OFF_ACTION_WITH_TRANSITION,
                "supports_transition": "{{true}}",
            },
            ConfigurationStyle.TRIGGER,
        ),
    ],
)
@pytest.mark.usefixtures("setup_light")
async def test_off_action_with_transition(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test off action with transition."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == LightEntityFeature.TRANSITION

    await _call_and_assert_action(
        hass, calls, SERVICE_TURN_OFF, {ATTR_TRANSITION: 2}, {ATTR_TRANSITION: 2}
    )

    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == LightEntityFeature.TRANSITION


@pytest.mark.parametrize(("count", "config"), [(1, ON_OFF_SET_LEVEL_ACTIONS)])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_light")
async def test_off_action_optimistic(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test off action with optimistic state."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_UNKNOWN
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0

    await _call_and_assert_action(hass, calls, SERVICE_TURN_OFF)

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_OFF
    assert state.attributes["color_mode"] is None
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ 1 == 1 }}", {})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_light")
async def test_level_action_no_template(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test setting brightness with optimistic template."""
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("brightness") is None

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {ATTR_BRIGHTNESS: 124},
        {ATTR_BRIGHTNESS: 124},
        "set_level",
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 124
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(("count", "extra_config"), [(1, ON_OFF_SET_LEVEL_ACTIONS)])
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
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_level_template(
    hass: HomeAssistant,
    expected_level: Any,
    expected_color_mode: ColorMode,
) -> None:
    """Test the template for the level."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("brightness") == expected_level
    assert state.state == STATE_ON

    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(("count", "extra_config"), [(1, ON_OFF_COLOR_TEMP_ACTIONS)])
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
        (2000, "{{500}}", ColorMode.COLOR_TEMP),
        (None, "{{501}}", ColorMode.COLOR_TEMP),
        (None, "{{x - 12}}", ColorMode.COLOR_TEMP),
        (None, "None", ColorMode.COLOR_TEMP),
        (None, "{{ none }}", ColorMode.COLOR_TEMP),
        (None, "", ColorMode.COLOR_TEMP),
        (None, "{{ 'one' }}", ColorMode.COLOR_TEMP),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_temperature_template(
    hass: HomeAssistant,
    expected_temp: Any,
    expected_color_mode: ColorMode,
) -> None:
    """Test the template for the temperature."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("color_temp_kelvin") == expected_temp
    assert state.state == STATE_ON
    assert state.attributes.get("color_mode") == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.COLOR_TEMP]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(("count", "extra_config"), [(1, ON_OFF_COLOR_TEMP_ACTIONS)])
@pytest.mark.parametrize(
    "style",
    [
        ConfigurationStyle.LEGACY,
        ConfigurationStyle.MODERN,
        ConfigurationStyle.TRIGGER,
    ],
)
@pytest.mark.usefixtures("setup_single_action_light")
async def test_temperature_action_no_template(
    hass: HomeAssistant,
    calls: list[ServiceCall],
) -> None:
    """Test setting temperature with optimistic template."""
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("color_template") is None

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {ATTR_COLOR_TEMP_KELVIN: 2898},
        {ATTR_COLOR_TEMP_KELVIN: 2898},
        "set_temperature",
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state is not None
    assert state.attributes.get("color_temp_kelvin") == 2898
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.COLOR_TEMP
    assert state.attributes["supported_color_modes"] == [ColorMode.COLOR_TEMP]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("count", "attribute_template", "extra_config"),
    [(1, "Template light", ON_OFF_SET_LEVEL_ACTIONS)],
)
@pytest.mark.parametrize(
    ("style", "attribute", "entity_id"),
    [
        (ConfigurationStyle.LEGACY, "friendly_name", TEST_LIGHT.entity_id),
        (ConfigurationStyle.MODERN, "name", "light.template_light"),
        (ConfigurationStyle.TRIGGER, "name", "light.template_light"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_friendly_name(hass: HomeAssistant, entity_id: str) -> None:
    """Test the accessibility of the friendly_name attribute."""

    state = hass.states.get(entity_id)
    assert state is not None

    assert state.attributes.get("friendly_name") == "Template light"


@pytest.mark.parametrize(("count", "extra_config"), [(1, ON_OFF_SET_LEVEL_ACTIONS)])
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
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_icon_template(hass: HomeAssistant) -> None:
    """Test icon template."""
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("icon") in ("", None)

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)

    assert state.attributes["icon"] == "mdi:check"


@pytest.mark.parametrize(("count", "extra_config"), [(1, ON_OFF_SET_LEVEL_ACTIONS)])
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
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_entity_picture_template(hass: HomeAssistant) -> None:
    """Test entity_picture template."""
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("entity_picture") in ("", None)

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["entity_picture"] == "/local/light.png"


@pytest.mark.parametrize(("count", "extra_config"), [(1, ON_OFF_LEGACY_COLOR_ACTIONS)])
@pytest.mark.parametrize(
    "style",
    [
        ConfigurationStyle.LEGACY,
    ],
)
@pytest.mark.usefixtures("setup_single_action_light")
async def test_legacy_color_action_no_template(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test setting color with optimistic template."""
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("hs_color") is None

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {ATTR_HS_COLOR: (40, 50)},
        {"h": 40, "s": 50},
        "set_color",
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.HS
    assert state.attributes.get("hs_color") == (40, 50)
    assert state.attributes["supported_color_modes"] == [ColorMode.HS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(
    ("count", "style", "extra_config", "attribute"),
    [
        (
            1,
            ConfigurationStyle.LEGACY,
            ON_OFF_LEGACY_COLOR_ACTIONS,
            "color_template",
        ),
    ],
)
@pytest.mark.parametrize(
    ("expected_hs", "attribute_template", "expected_color_mode"),
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
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_legacy_color_template(
    hass: HomeAssistant,
    expected_hs: tuple[float, float] | None,
    expected_color_mode: ColorMode,
) -> None:
    """Test the template for the color."""
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("hs_color") == expected_hs
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.HS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    (
        "extra_config",
        "attribute",
        "attribute_value",
        "expected_action",
        "expected_data",
        "expected_color_mode",
    ),
    [
        (
            ON_OFF_HS_ACTIONS,
            ATTR_HS_COLOR,
            (40, 50),
            "set_hs",
            {"h": 40, "s": 50},
            ColorMode.HS,
        ),
        (
            ON_OFF_RGB_ACTIONS,
            ATTR_RGB_COLOR,
            (160, 78, 192),
            "set_rgb",
            {"r": 160, "g": 78, "b": 192},
            ColorMode.RGB,
        ),
        (
            ON_OFF_RGBW_ACTIONS,
            ATTR_RGBW_COLOR,
            (160, 78, 192, 25),
            "set_rgbw",
            {"r": 160, "g": 78, "b": 192, "w": 25},
            ColorMode.RGBW,
        ),
        (
            ON_OFF_RGBWW_ACTIONS,
            ATTR_RGBWW_COLOR,
            (160, 78, 192, 25, 50),
            "set_rgbww",
            {"r": 160, "g": 78, "b": 192, "cw": 25, "ww": 50},
            ColorMode.RGBWW,
        ),
    ],
)
@pytest.mark.usefixtures("setup_single_action_light")
async def test_color_actions_no_template(
    hass: HomeAssistant,
    calls: list[ServiceCall],
    attribute: str,
    attribute_value: tuple[int | float, ...],
    expected_action: str,
    expected_data: dict[str, int | float],
    expected_color_mode: ColorMode,
) -> None:
    """Test setting colors with an optimistic template light."""
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get(attribute) is None

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {attribute: attribute_value},
        expected_data,
        expected_action,
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes.get(attribute) == attribute_value
    assert state.attributes["supported_color_modes"] == [expected_color_mode]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(("count", "extra_config"), [(1, ON_OFF_HS_ACTIONS)])
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
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_hs_template(
    hass: HomeAssistant,
    expected_hs: tuple[float, float] | None,
    expected_color_mode: ColorMode,
) -> None:
    """Test the template for the color."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("hs_color") == expected_hs
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.HS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(("count", "extra_config"), [(1, ON_OFF_RGB_ACTIONS)])
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
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_rgb_template(
    hass: HomeAssistant,
    expected_rgb: tuple[int, int, int] | None,
    expected_color_mode: ColorMode,
) -> None:
    """Test the template for the color."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("rgb_color") == expected_rgb
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.RGB]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(("count", "extra_config"), [(1, ON_OFF_RGBW_ACTIONS)])
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
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_rgbw_template(
    hass: HomeAssistant,
    expected_rgbw: tuple[int, int, int, int] | None,
    expected_color_mode: ColorMode,
) -> None:
    """Test the template for the color."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("rgbw_color") == expected_rgbw
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.RGBW]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(("count", "extra_config"), [(1, ON_OFF_RGBWW_ACTIONS)])
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
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_rgbww_template(
    hass: HomeAssistant,
    expected_rgbww: tuple[int, int, int, int, int] | None,
    expected_color_mode: ColorMode,
) -> None:
    """Test the template for the color."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("rgbww_color") == expected_rgbww
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.RGBWW]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("config", "style"),
    [
        (
            {
                **ON_OFF_ACTIONS,
                "value_template": "{{1 == 1}}",
                **ALL_COLOR_ACTIONS,
            },
            ConfigurationStyle.LEGACY,
        ),
        (
            {
                **ON_OFF_ACTIONS,
                "state": "{{1 == 1}}",
                **ALL_COLOR_ACTIONS,
            },
            ConfigurationStyle.MODERN,
        ),
        (
            {
                **ON_OFF_ACTIONS,
                "state": "{{1 == 1}}",
                **ALL_COLOR_ACTIONS,
            },
            ConfigurationStyle.TRIGGER,
        ),
    ],
)
@pytest.mark.usefixtures("setup_light")
async def test_all_colors_mode_no_template(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test setting color and color temperature with optimistic template."""
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("hs_color") is None

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {ATTR_HS_COLOR: (40, 50)},
        {"h": 40, "s": 50},
        "set_hs",
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["color_mode"] == ColorMode.HS
    assert state.attributes["color_temp_kelvin"] is None
    assert state.attributes["hs_color"] == (40, 50)
    assert state.attributes["supported_color_modes"] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
    ]
    assert state.attributes["supported_features"] == 0

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {ATTR_COLOR_TEMP_KELVIN: 8130},
        {ATTR_COLOR_TEMP_KELVIN: 8130, "color_temp": 123},
        "set_temperature",
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["color_mode"] == ColorMode.COLOR_TEMP
    assert state.attributes["color_temp_kelvin"] == 8130
    assert "hs_color" in state.attributes  # Color temp represented as hs_color
    assert state.attributes["supported_color_modes"] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
    ]
    assert state.attributes["supported_features"] == 0

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {ATTR_RGB_COLOR: (160, 78, 192)},
        {"r": 160, "g": 78, "b": 192},
        "set_rgb",
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["color_mode"] == ColorMode.RGB
    assert state.attributes["color_temp_kelvin"] is None
    assert state.attributes["rgb_color"] == (160, 78, 192)
    assert state.attributes["supported_color_modes"] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
    ]
    assert state.attributes["supported_features"] == 0

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {ATTR_RGBW_COLOR: (160, 78, 192, 25)},
        {"r": 160, "g": 78, "b": 192, "w": 25},
        "set_rgbw",
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["color_mode"] == ColorMode.RGBW
    assert state.attributes["color_temp_kelvin"] is None
    assert state.attributes["rgbw_color"] == (160, 78, 192, 25)
    assert state.attributes["supported_color_modes"] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
    ]
    assert state.attributes["supported_features"] == 0

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {ATTR_RGBWW_COLOR: (160, 78, 192, 25, 55)},
        {"r": 160, "g": 78, "b": 192, "cw": 25, "ww": 55},
        "set_rgbww",
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["color_mode"] == ColorMode.RGBWW
    assert state.attributes["color_temp_kelvin"] is None
    assert state.attributes["rgbww_color"] == (160, 78, 192, 25, 55)
    assert state.attributes["supported_color_modes"] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
    ]
    assert state.attributes["supported_features"] == 0

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {ATTR_HS_COLOR: (10, 20)},
        {"h": 10, "s": 20},
        "set_hs",
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["color_mode"] == ColorMode.HS
    assert state.attributes["color_temp_kelvin"] is None
    assert state.attributes["hs_color"] == (10, 20)
    assert state.attributes["supported_color_modes"] == [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
    ]
    assert state.attributes["supported_features"] == 0

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {ATTR_COLOR_TEMP_KELVIN: 4273},
        {ATTR_COLOR_TEMP_KELVIN: 4273, "color_temp": 234},
        "set_temperature",
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["color_mode"] == ColorMode.COLOR_TEMP
    assert state.attributes["color_temp_kelvin"] == 4273
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
@pytest.mark.usefixtures("setup_light_with_effects")
async def test_effect_action(
    hass: HomeAssistant, effect: str, expected: Any, calls: list[ServiceCall]
) -> None:
    """Test setting valid effect with template."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state is not None

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {ATTR_EFFECT: effect},
        {ATTR_EFFECT: effect},
        "set_effect",
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
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
@pytest.mark.usefixtures("setup_light_with_effects")
async def test_effect_list_template(
    hass: HomeAssistant, expected_effect_list: list[str] | None
) -> None:
    """Test the template for the effect list."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
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
@pytest.mark.usefixtures("setup_light_with_effects")
async def test_effect_template(
    hass: HomeAssistant, expected_effect: str | None
) -> None:
    """Test the template for the effect."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
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
    ("expected_max_kelvin", "attribute_template"),
    [
        (8474, "{{118}}"),
        (6535, "{{x - 12}}"),
        (6535, "None"),
        (6535, "{{ none }}"),
        (6535, ""),
        (6535, "{{ 'a' }}"),
    ],
)
@pytest.mark.usefixtures("setup_light_with_mireds")
async def test_min_mireds_template(
    hass: HomeAssistant, expected_max_kelvin: int
) -> None:
    """Test the template for the min mireds."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state is not None
    assert state.attributes.get("max_color_temp_kelvin") == expected_max_kelvin


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
    ("expected_min_kelvin", "attribute_template"),
    [
        (2049, "{{488}}"),
        (2000, "{{x - 12}}"),
        (2000, "None"),
        (2000, "{{ none }}"),
        (2000, ""),
        (2000, "{{ 'a' }}"),
    ],
)
@pytest.mark.usefixtures("setup_light_with_mireds")
async def test_max_mireds_template(
    hass: HomeAssistant,
    expected_min_kelvin: int,
) -> None:
    """Test the template for the max mireds."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state is not None
    assert state.attributes.get("min_color_temp_kelvin") == expected_min_kelvin


@pytest.mark.parametrize(("count", "extra_config"), [(1, ON_OFF_COLOR_TEMP_ACTIONS)])
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
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_supports_transition_template(
    hass: HomeAssistant,
    expected_supports_transition: bool,
) -> None:
    """Test the template for the supports transition."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LIGHT.entity_id)

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
@pytest.mark.usefixtures("setup_light_with_transition_template")
async def test_supports_transition_template_updates(hass: HomeAssistant) -> None:
    """Test the template for the supports transition dynamically."""
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state is not None

    hass.states.async_set("sensor.test", 0)
    await hass.async_block_till_done()

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LIGHT.entity_id)
    supported_features = state.attributes.get("supported_features")
    assert supported_features == LightEntityFeature.EFFECT

    hass.states.async_set("sensor.test", 1)
    await hass.async_block_till_done()

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_LIGHT.entity_id)
    supported_features = state.attributes.get("supported_features")
    assert (
        supported_features == LightEntityFeature.TRANSITION | LightEntityFeature.EFFECT
    )

    hass.states.async_set("sensor.test", 0)
    await hass.async_block_till_done()

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LIGHT.entity_id)
    supported_features = state.attributes.get("supported_features")
    assert supported_features == LightEntityFeature.EFFECT


@pytest.mark.parametrize(
    ("count", "extra_config", "attribute_template"),
    [
        (
            1,
            ON_OFF_SET_LEVEL_ACTIONS,
            "{{ is_state('binary_sensor.availability', 'on') }}",
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
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_available_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability templates with values from other entities."""
    # When template returns true..
    hass.states.async_set(TEST_AVAILABILITY_ENTITY, STATE_ON)
    await hass.async_block_till_done()

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    # Device State should not be unavailable
    assert hass.states.get(TEST_LIGHT.entity_id).state != STATE_UNAVAILABLE

    # When Availability template returns false
    hass.states.async_set(TEST_AVAILABILITY_ENTITY, STATE_OFF)
    await hass.async_block_till_done()

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    # device state should be unavailable
    assert hass.states.get(TEST_LIGHT.entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("count", "extra_config", "attribute_template"),
    [
        (
            1,
            ON_OFF_SET_LEVEL_ACTIONS,
            "{{ x - 12 }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "availability_template"),
        (ConfigurationStyle.MODERN, "availability"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog_setup_text
) -> None:
    """Test that an invalid availability keeps the device available."""
    assert hass.states.get(TEST_LIGHT.entity_id).state != STATE_UNAVAILABLE
    assert "UndefinedError: 'x' is undefined" in caplog_setup_text


@pytest.mark.parametrize("config", [ON_OFF_ACTIONS])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_unique_id(
    hass: HomeAssistant, style: ConfigurationStyle, config: ConfigType
) -> None:
    """Test unique_id option only creates one light per id."""
    await setup_and_test_unique_id(hass, TEST_LIGHT, style, config)


@pytest.mark.parametrize("config", [ON_OFF_ACTIONS])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_nested_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a template unique_id propagates to light unique_ids."""
    await setup_and_test_nested_unique_id(
        hass, TEST_LIGHT, style, entity_registry, config
    )


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
@pytest.mark.usefixtures("setup_empty_action_light")
async def test_empty_color_mode_action_config(
    hass: HomeAssistant, color_mode: ColorMode
) -> None:
    """Test empty actions for color mode actions."""
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["supported_color_modes"] == [color_mode]

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_LIGHT.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        light.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_LIGHT.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
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
@pytest.mark.usefixtures("setup_empty_action_light")
@pytest.mark.parametrize("action", ["set_effect"])
async def test_effect_with_empty_action(hass: HomeAssistant) -> None:
    """Test empty set_effect action."""
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["supported_features"] == LightEntityFeature.EFFECT


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "state": "{{ is_state('light.test_state', 'on') }}",
                "turn_on": [],
                "turn_off": [],
                "optimistic": True,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_light")
async def test_optimistic_option(hass: HomeAssistant) -> None:
    """Test optimistic yaml option."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        light.DOMAIN,
        "turn_on",
        {"entity_id": TEST_LIGHT.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_ON

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "state": "{{ is_state('light.test_state', 'on') }}",
                "turn_on": [],
                "turn_off": [],
                "optimistic": False,
            },
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "expected"),
    [
        (ConfigurationStyle.MODERN, STATE_OFF),
        (ConfigurationStyle.TRIGGER, STATE_UNKNOWN),
    ],
)
@pytest.mark.usefixtures("setup_light")
async def test_not_optimistic(hass: HomeAssistant, expected: str) -> None:
    """Test optimistic yaml option set to false."""
    await hass.services.async_call(
        light.DOMAIN,
        "turn_on",
        {"entity_id": TEST_LIGHT.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == expected


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests creating a light from a config entry."""

    hass.states.async_set(
        "sensor.test_sensor",
        "on",
        {},
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "state": "{{ states('sensor.test_sensor') }}",
            "turn_on": [],
            "turn_off": [],
            "template_type": light.DOMAIN,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.my_template")
    assert state is not None
    assert state == snapshot


async def test_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""

    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        light.DOMAIN,
        {
            "name": "My template",
            "state": "{{ 'on' }}",
            "turn_on": [],
            "turn_off": [],
        },
    )

    assert state["state"] == STATE_ON
