"""The tests for the  Template light platform."""

from enum import StrEnum
from itertools import chain
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_mock_restore_state_shutdown_restart,
)
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant import config as hass_config
from homeassistant.components import light, template
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    ColorMode,
    LightEntityCapabilityAttribute,
    LightEntityFeature,
    LightEntityStateAttribute,
)
from homeassistant.components.template.config import async_validate_config
from homeassistant.components.template.const import (
    LIGHT_DEPRECATED_OPTIONS,
    LIGHT_REQUIRED_ACTIONS_OPTIONS,
    WEATHER_DEPRECATED_OPTIONS,
    DeprecatedTemplateOptions,
    TemplateService,
)
from homeassistant.components.template.light import (
    DEFAULT_NAME,
    DEPRECATED_HELPER_MISSING_ACTIONS_ISSUE_ID,
    DEPRECATED_TEMPERATURE_ISSUE_ID,
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
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml_dict

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    assert_action,
    assert_attributes_template,
    assert_deprecated_missing_actions_issue,
    assert_extra_template_attributes,
    assert_invalid_config_entry_actions_do_not_create_entities,
    assert_invalid_yaml_actions_do_not_create_entities,
    assert_state_and_attributes,
    async_get_flow_preview_state,
    async_trigger,
    get_issues_with_prefix,
    make_test_action,
    make_test_trigger,
    setup_and_test_nested_unique_id,
    setup_and_test_unique_id,
    setup_entity,
    setup_mock_template_entity_restore_state,
    setup_restore_template_entity,
)

TEST_STATE_ENTITY_ID = "light.test_state"
TEST_SENSOR_STATE_ENTITY_ID = "sensor.test_state"
TEST_AVAILABILITY_ENTITY = "binary_sensor.availability"

TEST_LIGHT = TemplatePlatformSetup(
    light.DOMAIN,
    "test_light",
    make_test_trigger(
        TEST_STATE_ENTITY_ID,
        TEST_SENSOR_STATE_ENTITY_ID,
        TEST_AVAILABILITY_ENTITY,
    ),
)

ON_ACTION = make_test_action("turn_on")
OFF_ACTION = make_test_action("turn_off")
ON_OFF_ACTIONS = {
    **ON_ACTION,
    **OFF_ACTION,
}


BRIGHTNESS_DATA = {
    "brightness": "{{ brightness }}",
    "brightness_pct": "{{ brightness_pct }}",
}
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

XY_ACTION = make_test_action(
    "set_xy",
    {
        "x": "{{ x }}",
        "y": "{{ y }}",
    },
)
ON_OFF_XY_ACTIONS = {
    **ON_OFF_ACTIONS,
    **XY_ACTION,
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
    **XY_ACTION,
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
            "effect_list": effect_list_template,
            "effect": effect_template,
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
            "temperature": "{{ 200 }}",
            **make_test_action("set_temperature", {"color_temp": "{{ color_temp }}"}),
        },
        "{{ 1==1 }}",
        ON_OFF_ACTIONS,
    )


@pytest.fixture
async def setup_light_with_kelvin(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    attribute: str,
    attribute_template: str,
) -> None:
    """Do setup of light that uses kelvin."""
    await setup_entity(
        hass,
        TEST_LIGHT,
        style,
        count,
        {
            attribute: attribute_template,
            "temperature_kelvin": "{{ 3000 }}",
            **COLOR_TEMP_ACTION,
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
            "effect_list": "{{ ['Disco', 'Police'] }}",
            "effect": "{{ None }}",
            "supports_transition": transition_template,
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
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"), [(0, "{%- if false -%}", {})]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("brightness", "brightness_pct"),
    [(2, 1), (255, 100), (124, 49), (1, 0), (254, 100)],
)
@pytest.mark.usefixtures("setup_state_light")
async def test_level_action_no_template(
    hass: HomeAssistant, brightness: int, brightness_pct: int, calls: list[ServiceCall]
) -> None:
    """Test setting brightness with optimistic template."""
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("brightness") is None

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {ATTR_BRIGHTNESS: brightness},
        {ATTR_BRIGHTNESS: brightness, ATTR_BRIGHTNESS_PCT: brightness_pct},
        "set_level",
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == brightness
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    assert state.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize(("count", "extra_config"), [(1, ON_OFF_SET_LEVEL_ACTIONS)])
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
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
        (None, "{{ '1' * 400 }}", ColorMode.BRIGHTNESS),
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
    ("style", "attribute"),
    [
        (ConfigurationStyle.MODERN, "temperature_kelvin"),
        (ConfigurationStyle.TRIGGER, "temperature_kelvin"),
    ],
)
@pytest.mark.parametrize(
    ("expected_temp", "attribute_template"),
    [
        (2000, "{{ 2000 }}"),
        (6535, "{{ 6535 }}"),
        (3000, "{{ 3000.4 }}"),
        (2701, "{{ 2700.9 }}"),
        (None, "{{ 1999 }}"),
        (None, "{{ 6536 }}"),
        (None, "{{ true }}"),
        (None, "{{ x - 12 }}"),
        (None, "None"),
        (None, "{{ none }}"),
        (None, ""),
        (None, "{{ 'one' }}"),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_temperature_kelvin_template(
    hass: HomeAssistant, expected_temp: int | None
) -> None:
    """Test the template for the temperature in kelvin."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("color_temp_kelvin") == expected_temp
    assert state.state == STATE_ON
    assert state.attributes.get("color_mode") == ColorMode.COLOR_TEMP
    assert state.attributes["supported_color_modes"] == [ColorMode.COLOR_TEMP]


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("config", "expected_temp"),
    [
        pytest.param(
            {"temperature_kelvin": "{{ 1600 }}", "min_kelvin": "{{ 1500 }}"},
            1600,
            id="below_default_min",
        ),
        pytest.param(
            {"temperature_kelvin": "{{ 9000 }}", "max_kelvin": "{{ 10000 }}"},
            9000,
            id="above_default_max",
        ),
        pytest.param(
            {"temperature_kelvin": "{{ 2500 }}", "min_kelvin": "{{ 3000 }}"},
            None,
            id="below_min",
        ),
        pytest.param(
            {"temperature": "{{ 500 }}", "temperature_kelvin": "{{ 3000 }}"},
            3000,
            id="kelvin_over_mireds",
        ),
    ],
)
async def test_temperature_kelvin_range(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: ConfigType,
    expected_temp: int | None,
) -> None:
    """Test the temperature in kelvin against the configured range."""
    await setup_entity(
        hass, TEST_LIGHT, style, count, config, "{{ 1==1 }}", ON_OFF_COLOR_TEMP_ACTIONS
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("color_temp_kelvin") == expected_temp


@pytest.mark.parametrize("count", [0])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    "config",
    [
        {"min_mireds": "{{ 153 }}", "min_kelvin": "{{ 2000 }}"},
        {"min_mireds": "{{ 153 }}", "max_kelvin": "{{ 6500 }}"},
        {"max_mireds": "{{ 500 }}", "min_kelvin": "{{ 2000 }}"},
        {"max_mireds": "{{ 500 }}", "max_kelvin": "{{ 6500 }}"},
    ],
)
async def test_mireds_and_kelvin_range_invalid(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: ConfigType,
) -> None:
    """Test the color temperature range can not mix mireds and kelvin."""
    await setup_entity(
        hass, TEST_LIGHT, style, count, config, "{{ 1==1 }}", ON_OFF_COLOR_TEMP_ACTIONS
    )
    assert hass.states.get(TEST_LIGHT.entity_id) is None


def get_deprecated_mireds_options_issues(
    issue_registry: ir.IssueRegistry,
) -> list[ir.IssueEntry]:
    """Return the deprecated light mireds options issues."""
    return get_issues_with_prefix(
        issue_registry, LIGHT_DEPRECATED_OPTIONS.translation_key
    )


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("config", "options"),
    [
        pytest.param(
            {"temperature": "{{ 500 }}"},
            "- `temperature` → `temperature_kelvin`",
            id="temperature",
        ),
        pytest.param(
            {"temperature": "{{ 500 }}", "temperature_kelvin": "{{ 2000 }}"},
            "- `temperature` → `temperature_kelvin`",
            id="temperature_and_kelvin",
        ),
        pytest.param(
            {"min_mireds": "{{ 153 }}", "max_mireds": "{{ 500 }}"},
            "- `min_mireds` → `max_kelvin`\n- `max_mireds` → `min_kelvin`",
            id="mireds_range",
        ),
    ],
)
async def test_deprecated_mireds_options_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    count: int,
    style: ConfigurationStyle,
    config: ConfigType,
    options: str,
) -> None:
    """Test a repair issue is created for options in mireds."""
    await setup_entity(
        hass, TEST_LIGHT, style, count, config, "{{ 1==1 }}", ON_OFF_COLOR_TEMP_ACTIONS
    )
    issues = get_deprecated_mireds_options_issues(issue_registry)
    assert len(issues) == 1
    assert issues[0].breaks_in_ha_version == "2027.6.0"
    assert issues[0].is_fixable is False
    assert issues[0].severity == ir.IssueSeverity.WARNING
    assert issues[0].learn_more_url == (
        "https://www.home-assistant.io/integrations/template/#light"
    )
    assert issues[0].translation_key == LIGHT_DEPRECATED_OPTIONS.translation_key
    assert issues[0].translation_placeholders == {
        "identifier": f"name: {TEST_LIGHT.object_id}",
        "options": options,
    }


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    "config",
    [
        {
            "temperature_kelvin": "{{ 3000 }}",
            "min_kelvin": "{{ 2000 }}",
            "max_kelvin": "{{ 6500 }}",
        }
    ],
)
async def test_no_deprecated_mireds_options_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    count: int,
    style: ConfigurationStyle,
    config: ConfigType,
) -> None:
    """Test no repair issue is created for options in kelvin."""
    await setup_entity(
        hass, TEST_LIGHT, style, count, config, "{{ 1==1 }}", ON_OFF_COLOR_TEMP_ACTIONS
    )
    assert get_deprecated_mireds_options_issues(issue_registry) == []


MIREDS_YAML = """\
template:
  - light:
      - name: Test
        turn_on: []
        turn_off: []
        set_temperature: []
        temperature: "{{ 500 }}"
        max_mireds: "{{ 500 }}"
"""

KELVIN_YAML = """\
template:
  - light:
      - name: Test
        turn_on: []
        turn_off: []
        set_temperature: []
        temperature_kelvin: "{{ 2000 }}"
        min_kelvin: "{{ 2000 }}"
"""

WEATHER_LEGACY_YAML = """\
  - weather:
      - name: Weather
        condition_template: sunny
        temperature_template: "{{ 20 }}"
        humidity_template: "{{ 25 }}"
"""


async def _async_setup_yaml(hass: HomeAssistant, yaml_path: Path, yaml: str) -> None:
    """Write configuration.yaml and set up the template integration from it."""
    await hass.async_add_executor_job(yaml_path.write_text, yaml)
    config = await hass.async_add_executor_job(load_yaml_dict, yaml_path)
    assert await async_setup_component(hass, template.DOMAIN, config)
    await hass.async_block_till_done()


async def _async_reload_yaml(hass: HomeAssistant, yaml_path: Path, yaml: str) -> None:
    """Write configuration.yaml and reload the template entities from it."""
    await hass.async_add_executor_job(yaml_path.write_text, yaml)
    with patch.object(hass_config, "YAML_CONFIG_FILE", str(yaml_path)):
        await hass.services.async_call(
            template.DOMAIN, TemplateService.RELOAD, blocking=True
        )
    await hass.async_block_till_done()


async def test_deprecated_mireds_options_issue_file_and_line(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, tmp_path: Path
) -> None:
    """Test the repair lists file and line, and is removed after a fix."""
    hass.config.config_dir = str(tmp_path)
    yaml_path = tmp_path / "configuration.yaml"
    await _async_setup_yaml(hass, yaml_path, MIREDS_YAML)

    issues = get_deprecated_mireds_options_issues(issue_registry)
    assert len(issues) == 1
    assert issues[0].translation_placeholders == {
        "identifier": "name: Test",
        "options": (
            "- `configuration.yaml:7`: `temperature` → `temperature_kelvin`\n"
            "- `configuration.yaml:8`: `max_mireds` → `min_kelvin`"
        ),
    }

    await _async_reload_yaml(hass, yaml_path, KELVIN_YAML)

    assert get_deprecated_mireds_options_issues(issue_registry) == []


async def test_deprecated_mireds_options_issue_not_changed_by_config_check(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, tmp_path: Path
) -> None:
    """Test validating the configuration alone does not create or remove repairs."""
    hass.config.config_dir = str(tmp_path)
    yaml_path = tmp_path / "configuration.yaml"
    await _async_setup_yaml(hass, yaml_path, MIREDS_YAML)
    issues = get_deprecated_mireds_options_issues(issue_registry)
    assert len(issues) == 1

    await hass.async_add_executor_job(yaml_path.write_text, KELVIN_YAML)
    config = await hass.async_add_executor_job(load_yaml_dict, yaml_path)
    await async_validate_config(hass, config)

    assert get_deprecated_mireds_options_issues(issue_registry) == issues


async def test_deprecated_options_issues_per_platform(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, tmp_path: Path
) -> None:
    """Test fixing the light options keeps the weather repair, and the reverse."""
    hass.config.config_dir = str(tmp_path)
    yaml_path = tmp_path / "configuration.yaml"

    def issue_ids(deprecation: DeprecatedTemplateOptions) -> list[str]:
        return [
            issue.issue_id
            for issue in get_issues_with_prefix(
                issue_registry, deprecation.translation_key
            )
        ]

    await _async_setup_yaml(hass, yaml_path, MIREDS_YAML + WEATHER_LEGACY_YAML)
    light_issue_ids = issue_ids(LIGHT_DEPRECATED_OPTIONS)
    weather_issue_ids = issue_ids(WEATHER_DEPRECATED_OPTIONS)
    assert len(light_issue_ids) == 1
    assert len(weather_issue_ids) == 1

    await _async_reload_yaml(hass, yaml_path, KELVIN_YAML + WEATHER_LEGACY_YAML)
    assert issue_ids(LIGHT_DEPRECATED_OPTIONS) == []
    assert issue_ids(WEATHER_DEPRECATED_OPTIONS) == weather_issue_ids

    await _async_reload_yaml(hass, yaml_path, MIREDS_YAML)
    assert issue_ids(LIGHT_DEPRECATED_OPTIONS) == light_issue_ids
    assert issue_ids(WEATHER_DEPRECATED_OPTIONS) == []


async def test_deprecated_mireds_options_issue_blueprint(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test all instances of a light blueprint share one repair."""
    assert await async_setup_component(
        hass,
        template.DOMAIN,
        {
            template.DOMAIN: [
                {
                    "use_blueprint": {
                        "path": "test_light_with_mireds.yaml",
                        "input": {"sensor": sensor},
                    },
                    "name": name,
                }
                for sensor, name in (
                    ("sensor.first", "First"),
                    ("sensor.second", "Second"),
                )
            ]
        },
    )
    await hass.async_block_till_done()

    issues = get_deprecated_mireds_options_issues(issue_registry)
    assert len(issues) == 1
    assert (
        issues[0].translation_key == LIGHT_DEPRECATED_OPTIONS.blueprint_translation_key
    )
    assert issues[0].translation_placeholders == {
        "blueprint": "test_light_with_mireds.yaml",
        "options": (
            "- `blueprints/template/test_light_with_mireds.yaml:19`: "
            "`temperature` → `temperature_kelvin`\n"
            "- `blueprints/template/test_light_with_mireds.yaml:20`: "
            "`max_mireds` → `min_kelvin`"
        ),
    }


@pytest.mark.parametrize(("count", "extra_config"), [(1, ON_OFF_COLOR_TEMP_ACTIONS)])
@pytest.mark.parametrize(
    "style",
    [
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


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
        (
            ON_OFF_XY_ACTIONS,
            ATTR_XY_COLOR,
            (0.2, 0.5),
            "set_xy",
            {"x": 0.2, "y": 0.5},
            ColorMode.XY,
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


@pytest.mark.parametrize(
    ("count", "extra_config", "attribute"), [(1, ON_OFF_XY_ACTIONS, "xy")]
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("expected_color", "attribute_template", "expected_color_mode"),
    [
        ((0.2, 0.5), "{{(0.2, 0.5)}}", ColorMode.XY),
        ((0.2, 0.5), "(0.2, 0.5)", ColorMode.XY),
        ((0.2, 0.5), "{{[0.2, 0.5]}}", ColorMode.XY),
        (None, "{{(1.1, 0.5)}}", ColorMode.XY),
        (None, "{{(0.5, 1.1)}}", ColorMode.XY),
        (None, "{{(-0.1, 0.5)}}", ColorMode.XY),
        (None, "{{(0.5, -0.1)}}", ColorMode.XY),
        (None, "{{x - 12}}", ColorMode.XY),
        (None, "", ColorMode.XY),
        (None, "{{ none }}", ColorMode.XY),
        (None, "{{('one','two')}}", ColorMode.XY),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_light")
async def test_xy_template(
    hass: HomeAssistant,
    expected_color: tuple[float, float] | None,
    expected_color_mode: ColorMode,
) -> None:
    """Test the xy template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes.get("xy_color") == expected_color
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == expected_color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.XY]
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("config", "style"),
    [
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

    supported_color_modes = [
        ColorMode.COLOR_TEMP,
        ColorMode.HS,
        ColorMode.RGB,
        ColorMode.RGBW,
        ColorMode.RGBWW,
        ColorMode.XY,
    ]

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
    assert state.attributes["supported_color_modes"] == supported_color_modes
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
    assert state.attributes["supported_color_modes"] == supported_color_modes
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
    assert state.attributes["supported_color_modes"] == supported_color_modes
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
    assert state.attributes["supported_color_modes"] == supported_color_modes
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
    assert state.attributes["supported_color_modes"] == supported_color_modes
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
    assert state.attributes["supported_color_modes"] == supported_color_modes
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
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == 0

    await _call_and_assert_action(
        hass,
        calls,
        SERVICE_TURN_ON,
        {ATTR_XY_COLOR: (0.2, 0.5)},
        {"x": 0.2, "y": 0.5},
        "set_xy",
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["color_mode"] == ColorMode.XY
    assert state.attributes["xy_color"] == (0.2, 0.5)
    assert state.attributes["supported_color_modes"] == supported_color_modes
    assert state.attributes["supported_features"] == 0


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
        (ConfigurationStyle.MODERN, "min_mireds"),
        (ConfigurationStyle.TRIGGER, "min_mireds"),
    ],
)
@pytest.mark.parametrize(
    ("expected_max_kelvin", "attribute_template"),
    [
        (8474, "{{118}}"),
        (6535, "{{ 1000001 }}"),
        (6535, "{{ 0 }}"),
        (6535, "{{ -5 }}"),
        (6535, "{{ 'nan' | float }}"),
        (6535, "{{ 'inf' | float }}"),
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
        (ConfigurationStyle.MODERN, "max_mireds"),
        (ConfigurationStyle.TRIGGER, "max_mireds"),
    ],
)
@pytest.mark.parametrize(
    ("expected_min_kelvin", "attribute_template"),
    [
        (2049, "{{488}}"),
        (1, "{{ 1000000 }}"),
        (2000, "{{ 1000001 }}"),
        (2000, "{{ 0 }}"),
        (2000, "{{ -5 }}"),
        (2000, "{{ 'nan' | float }}"),
        (2000, "{{ 'inf' | float }}"),
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


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.MODERN, "min_kelvin"),
        (ConfigurationStyle.TRIGGER, "min_kelvin"),
    ],
)
@pytest.mark.parametrize(
    ("expected_min_kelvin", "attribute_template"),
    [
        (2500, "{{ 2500 }}"),
        (2000, "{{ 0 }}"),
        (2000, "{{ -5 }}"),
        (2000, "{{ 'nan' | float }}"),
        (2000, "{{ 'inf' | float }}"),
        (2000, "{{ x - 12 }}"),
        (2000, "None"),
        (2000, "{{ none }}"),
        (2000, ""),
        (2000, "{{ 'a' }}"),
    ],
)
@pytest.mark.usefixtures("setup_light_with_kelvin")
async def test_min_kelvin_template(
    hass: HomeAssistant, expected_min_kelvin: int
) -> None:
    """Test the template for the min kelvin."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state is not None
    assert state.attributes.get("min_color_temp_kelvin") == expected_min_kelvin


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.MODERN, "max_kelvin"),
        (ConfigurationStyle.TRIGGER, "max_kelvin"),
    ],
)
@pytest.mark.parametrize(
    ("expected_max_kelvin", "attribute_template"),
    [
        (5000, "{{ 5000 }}"),
        (6535, "{{ 0 }}"),
        (6535, "{{ -5 }}"),
        (6535, "{{ 'nan' | float }}"),
        (6535, "{{ 'inf' | float }}"),
        (6535, "{{ x - 12 }}"),
        (6535, "None"),
        (6535, "{{ none }}"),
        (6535, ""),
        (6535, "{{ 'a' }}"),
    ],
)
@pytest.mark.usefixtures("setup_light_with_kelvin")
async def test_max_kelvin_template(
    hass: HomeAssistant, expected_max_kelvin: int
) -> None:
    """Test the template for the max kelvin."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state is not None
    assert state.attributes.get("max_color_temp_kelvin") == expected_max_kelvin


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    "option", ["min_mireds", "max_mireds", "min_kelvin", "max_kelvin"]
)
@pytest.mark.parametrize(
    "value",
    [
        pytest.param("{{ x - 12 }}", id="template_error"),
        pytest.param("{{ 0 }}", id="zero"),
        pytest.param("{{ 'inf' | float }}", id="infinity"),
    ],
)
async def test_color_temp_range_template_error_rgbww(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    option: str,
    value: str,
) -> None:
    """Test an invalid range keeps the light working in RGBWW mode."""
    await setup_entity(
        hass,
        TEST_LIGHT,
        style,
        count,
        {
            option: value,
            "rgbww": "{{ (255, 0, 0, 10, 10) }}",
            **RGBWW_ACTION,
            **COLOR_TEMP_ACTION,
        },
        "{{ 1==1 }}",
        ON_OFF_ACTIONS,
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["color_mode"] == ColorMode.RGBWW
    assert state.attributes["min_color_temp_kelvin"] == 2000
    assert state.attributes["max_color_temp_kelvin"] == 6535


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("config", "first_bound", "second_bound"),
    [
        pytest.param(
            {
                "temperature_kelvin": "{{ 2500 }}",
                "min_kelvin": "{{ states('sensor.bound') | int }}",
            },
            3000,
            2000,
            id="kelvin",
        ),
        pytest.param(
            {
                "temperature": "{{ 400 }}",
                "max_mireds": "{{ states('sensor.bound') | int }}",
            },
            333,
            500,
            id="mireds",
        ),
    ],
)
async def test_temperature_revalidated_when_range_changes(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: ConfigType,
    first_bound: int,
    second_bound: int,
) -> None:
    """Test the temperature is revalidated when the range widens and narrows."""
    hass.states.async_set("sensor.bound", str(first_bound))
    await setup_entity(
        hass, TEST_LIGHT, style, count, config, "{{ 1==1 }}", ON_OFF_COLOR_TEMP_ACTIONS
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["color_temp_kelvin"] is None

    # The unchanged temperature becomes valid when the range widens
    hass.states.async_set("sensor.bound", str(second_bound))
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["color_temp_kelvin"] == 2500

    # And invalid again when the range narrows
    hass.states.async_set("sensor.bound", str(first_bound))
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["color_temp_kelvin"] is None


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_inverted_color_temp_range(
    hass: HomeAssistant, style: ConfigurationStyle, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an inverted range falls back to the default range and warns once."""
    await setup_entity(
        hass,
        TEST_LIGHT,
        style,
        1,
        {
            "temperature_kelvin": "{{ 4000 }}",
            "min_kelvin": "{{ 6000 }}",
            "max_kelvin": "{{ 3000 }}",
        },
        "{{ 1==1 }}",
        ON_OFF_COLOR_TEMP_ACTIONS,
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["min_color_temp_kelvin"] == 2000
    assert state.attributes["max_color_temp_kelvin"] == 6535
    assert state.attributes["color_temp_kelvin"] == 4000
    assert caplog.text.count("color temperature range of light.test_light") == 1


async def test_color_temp_range_moved_past_old_range(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test moving the whole range does not warn while one bound is updated."""
    hass.states.async_set("sensor.bound", "2000")
    await setup_entity(
        hass,
        TEST_LIGHT,
        ConfigurationStyle.MODERN,
        1,
        {
            "temperature_kelvin": "{{ 4500 }}",
            "min_kelvin": "{{ states('sensor.bound') | int }}",
            "max_kelvin": "{{ states('sensor.bound') | int + 1000 }}",
        },
        "{{ 1==1 }}",
        ON_OFF_COLOR_TEMP_ACTIONS,
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    assert hass.states.get(TEST_LIGHT.entity_id).attributes["color_temp_kelvin"] is None

    hass.states.async_set("sensor.bound", "4000")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["min_color_temp_kelvin"] == 4000
    assert state.attributes["max_color_temp_kelvin"] == 5000
    assert state.attributes["color_temp_kelvin"] == 4500
    assert "color temperature range" not in caplog.text


@pytest.mark.parametrize(
    ("hs_template", "first_mode", "expected_mode", "expected_temp"),
    [
        pytest.param(
            "{{ none }}", ColorMode.UNKNOWN, ColorMode.COLOR_TEMP, 2500, id="unknown"
        ),
        pytest.param(
            "{{ (360, 100) }}", ColorMode.HS, ColorMode.HS, None, id="keep_hs"
        ),
    ],
)
async def test_temperature_revalidated_color_mode(
    hass: HomeAssistant,
    hs_template: str,
    first_mode: ColorMode,
    expected_mode: ColorMode,
    expected_temp: int | None,
) -> None:
    """Test the color mode when the range widens on a multi color mode light."""
    hass.states.async_set("sensor.bound", "3000")
    await setup_entity(
        hass,
        TEST_LIGHT,
        ConfigurationStyle.MODERN,
        1,
        {
            "temperature_kelvin": "{{ 2500 }}",
            "min_kelvin": "{{ states('sensor.bound') | int }}",
            "hs": hs_template,
            **HS_ACTION,
        },
        "{{ 1==1 }}",
        ON_OFF_COLOR_TEMP_ACTIONS,
    )
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["color_mode"] == first_mode
    assert state.attributes.get("color_temp_kelvin") is None

    hass.states.async_set("sensor.bound", "2000")
    await hass.async_block_till_done()
    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state.attributes["color_mode"] == expected_mode
    assert state.attributes.get("color_temp_kelvin") == expected_temp


@pytest.mark.parametrize(("count", "extra_config"), [(1, ON_OFF_COLOR_TEMP_ACTIONS)])
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
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
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
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


async def _async_setup_light_config_entry(
    hass: HomeAssistant, options: dict[str, Any]
) -> MockConfigEntry:
    """Set up a template light config entry."""
    config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "turn_on": [],
            "turn_off": [],
            "set_temperature": [],
            "template_type": light.DOMAIN,
            **options,
        },
        title="My template",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


async def test_deprecated_temperature_config_entry_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a repair issue is tied to a helper that uses the temperature option."""
    config_entry = await _async_setup_light_config_entry(
        hass, {"temperature": "{{ 500 }}"}
    )
    issue_id = f"{DEPRECATED_TEMPERATURE_ISSUE_ID}_{config_entry.entry_id}"
    issue = issue_registry.async_get_issue(template.DOMAIN, issue_id)
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.config_entry_id == config_entry.entry_id
    assert issue.translation_key == DEPRECATED_TEMPERATURE_ISSUE_ID
    assert issue.translation_placeholders == {
        "name": "My template",
        "breaks_in_ha_version": "2027.6.0",
    }

    # Replacing the option with temperature_kelvin removes the issue
    options = {**config_entry.options, "temperature_kelvin": "{{ 2000 }}"}
    options.pop("temperature")
    hass.config_entries.async_update_entry(config_entry, options=options)
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(template.DOMAIN, issue_id) is None


async def test_deprecated_temperature_config_entry_removed(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the repair issue is removed with the helper."""
    config_entry = await _async_setup_light_config_entry(
        hass, {"temperature": "{{ 500 }}"}
    )
    issue_id = f"{DEPRECATED_TEMPERATURE_ISSUE_ID}_{config_entry.entry_id}"
    assert issue_registry.async_get_issue(template.DOMAIN, issue_id) is not None

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(template.DOMAIN, issue_id) is None


async def test_no_deprecated_temperature_config_entry_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test no repair issue is created for a helper using kelvin."""
    config_entry = await _async_setup_light_config_entry(
        hass, {"temperature_kelvin": "{{ 3000 }}"}
    )
    assert (
        issue_registry.async_get_issue(
            template.DOMAIN,
            f"{DEPRECATED_TEMPERATURE_ISSUE_ID}_{config_entry.entry_id}",
        )
        is None
    )


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


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    (
        "saved_state",
        "saved_extra_data",
        "initial_state",
        "initial_attributes",
    ),
    [
        (
            STATE_OFF,
            {
                "is_on": False,
                "brightness": None,
                "color_mode": "color_temp",
                "color_temp_kelvin": None,
                "effect_list": None,
                "effect": None,
                "hs_color": None,
                "max_color_temp_kelvin": 6535,
                "min_color_temp_kelvin": 2000,
                "rgb_color": None,
                "rgbw_color": None,
                "rgbww_color": None,
                "supported_color_modes": ["color_temp"],
                "xy_color": None,
            },
            STATE_OFF,
            {
                "brightness": None,
                "color_mode": None,
                "color_temp_kelvin": None,
                "effect_list": None,
                "effect": None,
                "max_color_temp_kelvin": 6535,
                "min_color_temp_kelvin": 2000,
                "rgb_color": None,
                "rgbw_color": None,
                "rgbww_color": None,
                "supported_color_modes": [ColorMode.COLOR_TEMP],
                "xy_color": None,
            },
        ),
        (
            # Missing key
            STATE_OFF,
            {
                "is_on": False,
                "brightness": None,
                "color_mode": "color_temp",
                "color_temp_kelvin": None,
                "effect_list": None,
                "effect": None,
                "hs_color": None,
                "max_color_temp_kelvin": 6535,
                "min_color_temp_kelvin": 2000,
                "rgb_color": None,
                "rgbw_color": None,
                "rgbww_color": None,
                "xy_color": None,
            },
            STATE_UNKNOWN,
            {},
        ),
        (
            # Bad color mode
            STATE_OFF,
            {
                "is_on": False,
                "brightness": None,
                "color_mode": "color_tem",
                "color_temp_kelvin": None,
                "effect_list": None,
                "effect": None,
                "hs_color": None,
                "max_color_temp_kelvin": 6535,
                "min_color_temp_kelvin": 2000,
                "rgb_color": None,
                "rgbw_color": None,
                "rgbww_color": None,
                "supported_color_modes": ["color_temp"],
                "xy_color": None,
            },
            STATE_UNKNOWN,
            {},
        ),
        (
            # Bad supported color modes
            STATE_OFF,
            {
                "is_on": False,
                "brightness": None,
                "color_mode": "color_temp",
                "color_temp_kelvin": None,
                "effect_list": None,
                "effect": None,
                "hs_color": None,
                "max_color_temp_kelvin": 6535,
                "min_color_temp_kelvin": 2000,
                "rgb_color": None,
                "rgbw_color": None,
                "rgbww_color": None,
                "supported_color_modes": ["color_tep"],
                "xy_color": None,
            },
            STATE_UNKNOWN,
            {},
        ),
        (
            STATE_UNAVAILABLE,
            {
                "is_on": False,
                "brightness": None,
                "color_mode": None,
                "color_temp_kelvin": None,
                "effect_list": None,
                "effect": None,
                "hs_color": None,
                "max_color_temp_kelvin": 6535,
                "min_color_temp_kelvin": 2000,
                "rgb_color": None,
                "rgbw_color": None,
                "rgbww_color": None,
                "supported_color_modes": ["onoff"],
                "xy_color": None,
            },
            STATE_UNKNOWN,
            {
                "brightness": None,
                "color_mode": None,
                "color_temp_kelvin": None,
                "effect_list": None,
                "effect": None,
                "max_color_temp_kelvin": 6535,
                "min_color_temp_kelvin": 2000,
                "rgb_color": None,
                "rgbw_color": None,
                "rgbww_color": None,
                "supported_color_modes": [
                    ColorMode.COLOR_TEMP,
                    ColorMode.HS,
                    ColorMode.RGB,
                    ColorMode.RGBW,
                    ColorMode.RGBWW,
                    ColorMode.XY,
                ],
                "xy_color": None,
            },
        ),
        (
            STATE_UNKNOWN,
            {
                "is_on": False,
                "brightness": None,
                "color_mode": None,
                "color_temp_kelvin": None,
                "effect_list": None,
                "effect": None,
                "hs_color": None,
                "max_color_temp_kelvin": 6535,
                "min_color_temp_kelvin": 2000,
                "rgb_color": None,
                "rgbw_color": None,
                "rgbww_color": None,
                "supported_color_modes": ["onoff"],
                "xy_color": None,
            },
            STATE_UNKNOWN,
            {
                "brightness": None,
                "color_mode": None,
                "color_temp_kelvin": None,
                "effect_list": None,
                "effect": None,
                "max_color_temp_kelvin": 6535,
                "min_color_temp_kelvin": 2000,
                "rgb_color": None,
                "rgbw_color": None,
                "rgbww_color": None,
                "supported_color_modes": [
                    ColorMode.COLOR_TEMP,
                    ColorMode.HS,
                    ColorMode.RGB,
                    ColorMode.RGBW,
                    ColorMode.RGBWW,
                    ColorMode.XY,
                ],
                "xy_color": None,
            },
        ),
    ],
)
async def test_restore_state(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    saved_state: str,
    saved_extra_data: dict | None,
    initial_state: str,
    initial_attributes: ConfigType,
) -> None:
    """Test restoring trigger template light."""

    restored_attributes = {  # These should be ignored
        "current_position": 5,
        "current_tilt_position": 5,
    }

    setup_mock_template_entity_restore_state(
        hass,
        TEST_LIGHT,
        saved_state,
        saved_extra_data=saved_extra_data,
        saved_attributes=restored_attributes,
    )

    await setup_restore_template_entity(
        hass,
        TEST_LIGHT,
        style,
        {
            "state": "{{ state_attr('sensor.test_state', 'is_on') }}",
            "turn_on": [],
            "turn_off": [],
            "level": "{{ state_attr('sensor.test_state', 'brightness') }}",
            "set_level": [],
            "temperature": "{{ state_attr('sensor.test_state', 'color_temp_kelvin') }}",
            "set_temperature": [],
            "effect_list": "{{ state_attr('sensor.test_state', 'effect_list') }}",
            "effect": "{{ state_attr('sensor.test_state', 'effect') }}",
            "set_effect": [],
            "hs": "{{ state_attr('sensor.test_state', 'hs_color') }}",
            "set_hs": [],
            "min_mireds": "{{ state_attr('sensor.test_state', 'max_color_temp_kelvin') }}",
            "max_mireds": "{{ state_attr('sensor.test_state', 'min_color_temp_kelvin') }}",
            "rgb": "{{ state_attr('sensor.test_state', 'rgb_color') }}",
            "set_rgb": [],
            "rgbw": "{{ state_attr('sensor.test_state', 'rgbw_color') }}",
            "set_rgbw": [],
            "rgbww": "{{ state_attr('sensor.test_state', 'rgbww_color') }}",
            "set_rgbww": [],
            "xy": "{{ state_attr('sensor.test_state', 'xy_color') }}",
            "set_xy": [],
        },
        "state_attr('sensor.test_state', 'is_on') is true",
    )

    assert_state_and_attributes(
        hass,
        TEST_LIGHT,
        initial_state,
        initial_attributes,
    )

    await async_trigger(
        hass,
        "sensor.test_state",
        "anything",
        {"is_on": True},
    )

    assert_state_and_attributes(hass, TEST_LIGHT, STATE_ON)


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_saving_state(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    hass_storage: dict[str, Any],
) -> None:
    """Test restore saved state."""

    await setup_entity(
        hass,
        TEST_LIGHT,
        style,
        1,
        config={
            "state": "{{ state_attr('light.test_state', 'is_on') }}",
            "turn_on": [],
            "turn_off": [],
            "level": "{{ state_attr('light.test_state', 'brightness') }}",
            "set_level": [],
        },
    )

    await async_trigger(
        hass,
        TEST_STATE_ENTITY_ID,
        "anything",
        {"is_on": True, "brightness": 255},
    )

    assert_state_and_attributes(
        hass,
        TEST_LIGHT,
        STATE_ON,
        {
            "brightness": 255,
            "color_mode": ColorMode.BRIGHTNESS,
            "supported_color_modes": [ColorMode.BRIGHTNESS],
        },
    )

    await async_mock_restore_state_shutdown_restart(hass)

    assert len(hass_storage[RESTORE_STATE_KEY]["data"]) == 1
    state = hass_storage[RESTORE_STATE_KEY]["data"][0]["state"]
    assert state["entity_id"] == TEST_LIGHT.entity_id

    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]
    assert extra_data == {
        "is_on": True,
        "brightness": 255,
        "color_mode": "brightness",
        "color_temp_kelvin": None,
        "effect_list": None,
        "effect": None,
        "hs_color": None,
        "max_color_temp_kelvin": 6535,
        "min_color_temp_kelvin": 2000,
        "rgb_color": None,
        "rgbw_color": None,
        "rgbww_color": None,
        "supported_color_modes": ["brightness"],
        "xy_color": None,
    }


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("action", "config"),
    [
        ("turn_on", {"turn_off": []}),
        ("turn_off", {"turn_on": []}),
        (
            "set_effect",
            {
                "effect_list": "{{ ['Disco', 'Police'] }}",
                "effect": "{{ None }}",
                **ON_OFF_ACTIONS,
            },
        ),
        ("set_hs", ON_OFF_ACTIONS),
        ("set_level", ON_OFF_ACTIONS),
        ("set_rgb", ON_OFF_ACTIONS),
        ("set_rgbw", ON_OFF_ACTIONS),
        ("set_rgbww", ON_OFF_ACTIONS),
        ("set_temperature", ON_OFF_ACTIONS),
        ("set_xy", ON_OFF_ACTIONS),
    ],
)
async def test_invalid_yaml_actions_do_not_create_entities(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    action: str,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid yaml actions do not create entities."""
    await assert_invalid_yaml_actions_do_not_create_entities(
        hass, TEST_LIGHT, style, config, action, caplog
    )


@pytest.mark.parametrize(
    ("action", "config"),
    [
        ("turn_on", {"turn_off": []}),
        ("turn_off", {"turn_on": []}),
        (
            "set_effect",
            {
                "effect_list": "{{ ['Disco', 'Police'] }}",
                "effect": "{{ None }}",
                **ON_OFF_ACTIONS,
            },
        ),
        ("set_hs", ON_OFF_ACTIONS),
        ("set_level", ON_OFF_ACTIONS),
        ("set_rgb", ON_OFF_ACTIONS),
        ("set_rgbw", ON_OFF_ACTIONS),
        ("set_rgbww", ON_OFF_ACTIONS),
        ("set_temperature", ON_OFF_ACTIONS),
        ("set_xy", ON_OFF_ACTIONS),
    ],
)
async def test_invalid_config_entry_actions_do_not_create_entities(
    hass: HomeAssistant,
    action: str,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid config entry actions do not create entities."""
    await assert_invalid_config_entry_actions_do_not_create_entities(
        hass, TEST_LIGHT, config, action, caplog
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_extra_template_attributes(
    hass: HomeAssistant, style: ConfigurationStyle
) -> None:
    """Test extra attributes."""
    await assert_extra_template_attributes(
        hass, TEST_LIGHT, style, {"state": "{{ 'on' }}", **ON_OFF_ACTIONS}
    )


@pytest.mark.parametrize(
    "attribute",
    list(chain(LightEntityCapabilityAttribute, LightEntityStateAttribute)),
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_blocked_template_attributes(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    attribute,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test blocked extra attributes."""
    await setup_entity(
        hass,
        TEST_LIGHT,
        style,
        0,
        {
            "state": "{{ 'on' }}",
            **ON_OFF_ACTIONS,
            "attributes": {str(attribute): "{{ 'does not matter' }}"},
        },
    )
    assert (
        f"Unsupported attribute(s) found for {DEFAULT_NAME}: {attribute}" in caplog.text
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_attributes_template(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes as a single template."""
    await assert_attributes_template(
        hass,
        TEST_LIGHT,
        style,
        {"state": "{{ 'on' }}", **ON_OFF_ACTIONS},
        caplog,
    )


@pytest.mark.parametrize(
    "attribute",
    list(chain(LightEntityCapabilityAttribute, LightEntityStateAttribute)),
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_attributes_template_with_blocked_attributes(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    attribute: StrEnum,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test blocked attributes for a single attributes template."""
    await setup_entity(
        hass,
        TEST_LIGHT,
        style,
        1,
        {
            "state": "{{ 'on' }}",
            **ON_OFF_ACTIONS,
            "attributes": f"{{{{ dict({attribute}='does not matter') }}}}",
        },
    )

    await async_trigger(hass, "sensor.test_extra_attributes", "anything")

    error = f"Unsupported attribute(s) found for {TEST_LIGHT.entity_id}: {attribute}"
    assert error in caplog.text


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "effect_list": "{{ ['off', 'disco', 'rainbow'] }}",
                **SET_EFFECT_ACTION,
                **ON_OFF_ACTIONS,
            },
        ),
    ],
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("off", "off"),
        ("disco", "disco"),
        ("rainbow", "rainbow"),
    ],
)
@pytest.mark.usefixtures("setup_light")
async def test_optimistic_effect(
    hass: HomeAssistant,
    mode: str,
    expected: Any,
    calls: list[ServiceCall],
) -> None:
    """Test optimistic effect."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    await _call_and_assert_action(
        hass, calls, SERVICE_TURN_ON, {"effect": mode}, {"effect": mode}, "set_effect"
    )

    state = hass.states.get(TEST_LIGHT.entity_id)
    assert state is not None
    assert state.attributes.get("effect") == expected


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("extra_config", "options"),
    [
        ({"hs": "{{ (40, 50) }}"}, "- `hs` requires `set_hs`"),
        ({"level": "{{ 100 }}"}, "- `level` requires `set_level`"),
        ({"rgb": "{{ (160, 78, 192) }}"}, "- `rgb` requires `set_rgb`"),
        ({"rgbw": "{{ (160, 78, 192, 25) }}"}, "- `rgbw` requires `set_rgbw`"),
        (
            {"rgbww": "{{ (160, 78, 192, 25, 50) }}"},
            "- `rgbww` requires `set_rgbww`",
        ),
        ({"temperature": "{{ 250 }}"}, "- `temperature` requires `set_temperature`"),
        (
            {"temperature_kelvin": "{{ 3000 }}"},
            "- `temperature_kelvin` requires `set_temperature`",
        ),
        ({"xy": "{{ (0.2, 0.5) }}"}, "- `xy` requires `set_xy`"),
    ],
)
async def test_deprecated_missing_actions_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    style: ConfigurationStyle,
    extra_config: ConfigType,
    options: str,
) -> None:
    """Test a repair is created for an option without its action."""
    await setup_entity(
        hass, TEST_LIGHT, style, 1, ON_OFF_ACTIONS, extra_config=extra_config
    )
    assert_deprecated_missing_actions_issue(
        issue_registry, LIGHT_REQUIRED_ACTIONS_OPTIONS, TEST_LIGHT, options
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("config", "extra_config"),
    [
        (ON_OFF_HS_ACTIONS, {"hs": "{{ (40, 50) }}"}),
        (ON_OFF_SET_LEVEL_ACTIONS, {"level": "{{ 100 }}"}),
        (ON_OFF_RGB_ACTIONS, {"rgb": "{{ (160, 78, 192) }}"}),
        (ON_OFF_RGBW_ACTIONS, {"rgbw": "{{ (160, 78, 192, 25) }}"}),
        (ON_OFF_RGBWW_ACTIONS, {"rgbww": "{{ (160, 78, 192, 25, 50) }}"}),
        (ON_OFF_COLOR_TEMP_ACTIONS, {"temperature": "{{ 250 }}"}),
        (ON_OFF_COLOR_TEMP_ACTIONS, {"temperature_kelvin": "{{ 3000 }}"}),
        (ON_OFF_XY_ACTIONS, {"xy": "{{ (0.2, 0.5) }}"}),
        (ON_OFF_SET_LEVEL_ACTIONS, {}),
    ],
)
async def test_no_deprecated_missing_actions_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    style: ConfigurationStyle,
    config: ConfigType,
    extra_config: ConfigType,
) -> None:
    """Test no repair is created when options have their action."""
    await setup_entity(hass, TEST_LIGHT, style, 1, config, extra_config=extra_config)
    assert (
        get_issues_with_prefix(
            issue_registry, LIGHT_REQUIRED_ACTIONS_OPTIONS.translation_key
        )
        == []
    )


MISSING_ACTIONS_YAML = """\
template:
  - light:
      - name: Test
        turn_on: []
        turn_off: []
        level: "{{ 100 }}"
        hs: "{{ (40, 50) }}"
        set_hs: []
"""


async def test_deprecated_missing_actions_issue_file_and_line(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, tmp_path: Path
) -> None:
    """Test the repair lists file and line, and is removed after a fix."""
    hass.config.config_dir = str(tmp_path)
    yaml_path = tmp_path / "configuration.yaml"
    await _async_setup_yaml(hass, yaml_path, MISSING_ACTIONS_YAML)

    issues = get_issues_with_prefix(
        issue_registry, LIGHT_REQUIRED_ACTIONS_OPTIONS.translation_key
    )
    assert len(issues) == 1
    assert issues[0].translation_placeholders == {
        "identifier": "name: Test",
        "options": "- `configuration.yaml:6`: `level` requires `set_level`",
    }

    await _async_reload_yaml(
        hass, yaml_path, MISSING_ACTIONS_YAML + "        set_level: []\n"
    )

    assert (
        get_issues_with_prefix(
            issue_registry, LIGHT_REQUIRED_ACTIONS_OPTIONS.translation_key
        )
        == []
    )


async def test_deprecated_missing_actions_config_entry_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a repair issue is tied to a helper with options without actions."""
    config_entry = await _async_setup_light_config_entry(
        hass,
        {
            "level": "{{ 100 }}",
            "hs": "{{ (40, 50) }}",
            "temperature_kelvin": "{{ 3000 }}",
        },
    )
    issue_id = f"{DEPRECATED_HELPER_MISSING_ACTIONS_ISSUE_ID}_{config_entry.entry_id}"
    issue = issue_registry.async_get_issue(template.DOMAIN, issue_id)
    assert issue is not None
    assert issue.breaks_in_ha_version == "2027.6.0"
    assert issue.config_entry_id == config_entry.entry_id
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_key == DEPRECATED_HELPER_MISSING_ACTIONS_ISSUE_ID
    assert issue.translation_placeholders == {
        "name": "My template",
        "breaks_in_ha_version": "2027.6.0",
        "options": "- `hs` requires `set_hs`\n- `level` requires `set_level`",
    }

    hass.config_entries.async_update_entry(
        config_entry,
        options={**config_entry.options, "set_hs": [], "set_level": []},
    )
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(template.DOMAIN, issue_id) is None


async def test_deprecated_missing_actions_config_entry_removed(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the repair issue is removed with the helper."""
    config_entry = await _async_setup_light_config_entry(hass, {"level": "{{ 100 }}"})
    issue_id = f"{DEPRECATED_HELPER_MISSING_ACTIONS_ISSUE_ID}_{config_entry.entry_id}"
    assert issue_registry.async_get_issue(template.DOMAIN, issue_id) is not None

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(template.DOMAIN, issue_id) is None


async def test_no_deprecated_missing_actions_config_entry_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test no repair issue is created for a helper with all actions."""
    config_entry = await _async_setup_light_config_entry(
        hass, {"level": "{{ 100 }}", "set_level": []}
    )
    assert (
        issue_registry.async_get_issue(
            template.DOMAIN,
            f"{DEPRECATED_HELPER_MISSING_ACTIONS_ISSUE_ID}_{config_entry.entry_id}",
        )
        is None
    )
