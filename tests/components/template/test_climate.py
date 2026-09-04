"""The tests for the Template climate platform."""

from typing import Any

import pytest

from homeassistant.components import climate
from homeassistant.components.climate import ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    async_trigger,
    make_test_action,
    make_test_trigger,
    setup_entity,
)

TEST_STATE_ENTITY_ID = "climate.test_state"
TEST_ATTRIBUTE_ENTITY_ID = "sensor.test_attribute"
TEST_AVAILABILITY_ENTITY = "binary_sensor.availability"

TEST_CLIMATE = TemplatePlatformSetup(
    climate.DOMAIN,
    "test_climate",
    make_test_trigger(
        TEST_STATE_ENTITY_ID,
        TEST_AVAILABILITY_ENTITY,
        TEST_ATTRIBUTE_ENTITY_ID,
    ),
)

SET_FAN_MODE_ACTION = make_test_action(
    "set_fan_mode",
    {
        "fan_mode": "{{ fan_mode }}",
    },
)
SET_HUMIDITY_ACTION = make_test_action(
    "set_humidity",
    {
        "humidity": "{{ humidity }}",
    },
)
SET_HVAC_MODE_ACTION = make_test_action(
    "set_hvac_mode",
    {
        "hvac_mode": "{{ hvac_mode }}",
    },
)
SET_PRESET_MODE_ACTION = make_test_action(
    "set_preset_mode",
    {
        "preset_mode": "{{ preset_mode }}",
    },
)
SET_SWING_HORIZONTAL_MODE_ACTION = make_test_action(
    "set_swing_horizontal_mode",
    {
        "swing_horizontal_mode": "{{ swing_horizontal_mode }}",
    },
)
SET_SWING_MODE_ACTION = make_test_action(
    "set_swing_mode",
    {
        "swing_mode": "{{ swing_mode }}",
    },
)
SET_TEMPERATURE_ACTION = make_test_action(
    "set_temperature",
    {
        "temperature": "{{ temperature }}",
        "target_temp_high": "{{ target_temp_high }}",
        "target_temp_low": "{{ target_temp_low }}",
        "hvac_mode": "{{ hvac_mode }}",
    },
)

MINIMUM_REQUIREMENTS = {
    "hvac_modes": "{{ ['off', 'heat', 'cool', 'heat_cool'] }}",
    **SET_HVAC_MODE_ACTION,
}


@pytest.fixture
async def setup_base_climate(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: dict[str, Any],
) -> None:
    """Do setup of climate integration."""
    await setup_entity(hass, TEST_CLIMATE, style, count, config)


@pytest.fixture
async def setup_climate(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: dict[str, Any],
    extra_config: dict[str, Any],
) -> None:
    """Do setup of climate integration."""
    await setup_entity(hass, TEST_CLIMATE, style, 1, config, extra_config=extra_config)


@pytest.fixture
async def setup_single_attribute_climate(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    attribute: str,
    attribute_template: str,
    extra_config: dict,
) -> None:
    """Do setup of climate integration."""
    await setup_entity(
        hass,
        TEST_CLIMATE,
        style,
        1,
        {attribute: attribute_template} if attribute and attribute_template else {},
        extra_config=extra_config,
    )


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [("current_humidity", MINIMUM_REQUIREMENTS)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        ("{{ 20 }}", 20),
        ("{{ 30 }}", 30),
        ("{{ 45 }}", 45),
        ("{{ 99 }}", 99),
        ("{{ 100 }}", 100),
        ("{{ 45.5 }}", 45),
        ("{{ -1 }}", None),
        ("{{ 101 }}", None),
        ("{{ True }}", None),
        ("{{ False }}", None),
        ("{{ 'something' }}", None),
        ("{{ x - 1 }}", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_climate")
async def test_humidity_template(hass: HomeAssistant, expected: Any) -> None:
    """Test template humidity."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.attributes.get("current_humidity") == expected


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [("current_temperature", MINIMUM_REQUIREMENTS)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        ("{{ -1 }}", -1),
        ("{{ 5.3423 }}", 5.3),
        ("{{ 30 }}", 30),
        ("{{ 45 }}", 45),
        ("{{ 99 }}", 99),
        ("{{ 100 }}", 100),
        ("{{ 45.5 }}", 45.5),
        ("{{ True }}", None),
        ("{{ False }}", None),
        ("{{ 'something' }}", None),
        ("{{ x - 1 }}", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_climate")
async def test_temperature_template(hass: HomeAssistant, expected: Any) -> None:
    """Test template temperature."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.attributes.get("current_temperature") == expected


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [("hvac_action", MINIMUM_REQUIREMENTS)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        ("{{ 'cooling' }}", HVACAction.COOLING),
        ("{{ 'defrosting' }}", HVACAction.DEFROSTING),
        ("{{ 'drying' }}", HVACAction.DRYING),
        ("{{ 'fan' }}", HVACAction.FAN),
        ("{{ 'heating' }}", HVACAction.HEATING),
        ("{{ 'idle' }}", HVACAction.IDLE),
        ("{{ 'off' }}", HVACAction.OFF),
        ("{{ 'preheating' }}", HVACAction.PREHEATING),
        ("{{ 100 }}", None),
        ("{{ 45.5 }}", None),
        ("{{ True }}", None),
        ("{{ False }}", None),
        ("{{ 'something' }}", None),
        ("{{ x - 1 }}", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_climate")
async def test_hvac_action_template(hass: HomeAssistant, expected: Any) -> None:
    """Test template hvac_action."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.attributes.get("hvac_action") == expected


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [
        (
            "target_humidity",
            {
                "min_humidity": 19,
                "max_humidity": 100,
                **SET_HUMIDITY_ACTION,
                **MINIMUM_REQUIREMENTS,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        ("{{ 20 }}", 20),
        ("{{ 30 }}", 30),
        ("{{ 45 }}", 45),
        ("{{ 99 }}", 99),
        ("{{ 100 }}", 100),
        ("{{ 45.5 }}", 45),
        ("{{ -1 }}", None),
        ("{{ 101 }}", None),
        ("{{ True }}", None),
        ("{{ False }}", None),
        ("{{ 'something' }}", None),
        ("{{ x - 1 }}", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_climate")
async def test_target_humidity_template(hass: HomeAssistant, expected: Any) -> None:
    """Test template target_humidity."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.attributes.get("humidity") == expected


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [
        (
            "target_temperature",
            {
                "min_temp": -2,
                "max_temp": 101,
                **SET_TEMPERATURE_ACTION,
                **MINIMUM_REQUIREMENTS,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        ("{{ -1 }}", -1),
        ("{{ 5.3423 }}", 5.3),
        ("{{ 30 }}", 30),
        ("{{ 45 }}", 45),
        ("{{ 99 }}", 99),
        ("{{ 100 }}", 100),
        ("{{ 45.5 }}", 45.5),
        ("{{ -3 }}", None),
        ("{{ 103 }}", None),
        ("{{ True }}", None),
        ("{{ False }}", None),
        ("{{ 'something' }}", None),
        ("{{ x - 1 }}", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_climate")
async def test_target_temperature_template(hass: HomeAssistant, expected: Any) -> None:
    """Test template target_temperature."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.attributes.get("temperature") == expected


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [
        (
            "target_temperature_high",
            {
                "min_temp": -3,
                "max_temp": 101,
                "target_temperature_low": "{{ -3 }}",
                **SET_TEMPERATURE_ACTION,
                **MINIMUM_REQUIREMENTS,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        ("{{ -1 }}", -1),
        ("{{ 5.3423 }}", 5.3),
        ("{{ 30 }}", 30),
        ("{{ 45 }}", 45),
        ("{{ 99 }}", 99),
        ("{{ 100 }}", 100),
        ("{{ 45.5 }}", 45.5),
        ("{{ -4 }}", None),
        ("{{ 103 }}", None),
        ("{{ True }}", None),
        ("{{ False }}", None),
        ("{{ 'something' }}", None),
        ("{{ x - 1 }}", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_climate")
async def test_target_temperature_high_template(
    hass: HomeAssistant, expected: Any
) -> None:
    """Test template target_temperature_high."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.attributes.get("target_temp_high") == expected


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [
        (
            "target_temperature_low",
            {
                "min_temp": -2,
                "max_temp": 102,
                "target_temperature_high": "{{ 102 }}",
                **SET_TEMPERATURE_ACTION,
                **MINIMUM_REQUIREMENTS,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        ("{{ -1 }}", -1),
        ("{{ 5.3423 }}", 5.3),
        ("{{ 30 }}", 30),
        ("{{ 45 }}", 45),
        ("{{ 99 }}", 99),
        ("{{ 100 }}", 100),
        ("{{ 45.5 }}", 45.5),
        ("{{ -3 }}", None),
        ("{{ 103 }}", None),
        ("{{ True }}", None),
        ("{{ False }}", None),
        ("{{ 'something' }}", None),
        ("{{ x - 1 }}", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_climate")
async def test_target_temperature_low_template(
    hass: HomeAssistant, expected: Any
) -> None:
    """Test template target_temperature_low."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.attributes.get("target_temp_low") == expected


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    "config",
    [
        {"target_temperature_high": 30, **MINIMUM_REQUIREMENTS},
        {"target_temperature_low": 30, **MINIMUM_REQUIREMENTS},
    ],
)
async def test_bad_target_temperature_range_config(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a bad target temperature range configuration."""
    platform = TEST_CLIMATE
    await setup_entity(hass, platform, style, 0, config)
    assert len(hass.states.async_all(platform.domain)) == 0
    assert (
        "Invalid config for 'template': some but not all values in the same group of inclusion 'temperature_limits'"
        in caplog.text
    )


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [("hvac_modes", SET_HVAC_MODE_ACTION)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        (
            "{{ ['off', 'heat', 'cool', 'heat_cool'] }}",
            [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.HEAT_COOL],
        ),
        (
            "{{ ['dry', 'auto', 'fan_only'] }}",
            [HVACMode.DRY, HVACMode.AUTO, HVACMode.FAN_ONLY],
        ),
        ("{{ [] }}", []),
        ("{{ '[]' }}", []),
        (
            "{{ ['dry', 'auto2', 'fan_only'] }}",
            [HVACMode.DRY, HVACMode.FAN_ONLY],
        ),
        ("{{ -3 }}", []),
        ("{{ 103.3 }}", []),
        ("{{ True }}", []),
        ("{{ False }}", []),
        ("{{ 'something' }}", []),
        ("{{ x - 1 }}", []),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_climate")
async def test_hvac_modes_template(
    hass: HomeAssistant, attribute: str, expected: Any
) -> None:
    """Test hvac_modes template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.attributes.get(attribute) == expected


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [
        (
            "hvac_mode",
            {
                "hvac_modes": "{{ ['off', 'heat', 'cool', 'heat_cool', 'dry', 'auto'] }}",
                **SET_HVAC_MODE_ACTION,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        ("{{ 'off' }}", HVACMode.OFF),
        ("{{ 'heat' }}", HVACMode.HEAT),
        ("{{ 'cool' }}", HVACMode.COOL),
        ("{{ 'heat_cool' }}", HVACMode.HEAT_COOL),
        ("{{ 'dry' }}", HVACMode.DRY),
        ("{{ 'auto' }}", HVACMode.AUTO),
        ("{{ 'fan_only' }}", STATE_UNKNOWN),
        ("{{ -3 }}", STATE_UNKNOWN),
        ("{{ 103.3 }}", STATE_UNKNOWN),
        ("{{ True }}", STATE_UNKNOWN),
        ("{{ False }}", STATE_UNKNOWN),
        ("{{ 'something' }}", STATE_UNKNOWN),
        ("{{ x - 1 }}", STATE_UNAVAILABLE),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_climate")
async def test_hvac_mode_template(hass: HomeAssistant, expected: Any) -> None:
    """Test hvac_mode template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.state == expected


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("config", "option"),
    [
        (
            SET_HVAC_MODE_ACTION,
            "hvac_modes",
        ),
        (
            {
                "hvac_modes": "{{ ['off', 'heat', 'cool', 'heat_cool', 'dry', 'auto', 'fan_only'] }}",
            },
            "set_hvac_mode",
        ),
    ],
)
async def test_required_hvac_mode_options(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    option: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test missing required options."""
    platform = TEST_CLIMATE
    await setup_entity(hass, platform, style, 0, config)
    assert len(hass.states.async_all(platform.domain)) == 0
    assert (
        f"Invalid config for 'template': required key '{option}' not provided"
        in caplog.text
    )


@pytest.mark.parametrize(
    ("attribute", "attribute_template", "extra_config"),
    [
        (
            "hvac_modes",
            "{{ state_attr('sensor.test_attribute', 'hvac_modes') or [] }}",
            SET_HVAC_MODE_ACTION,
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_single_attribute_climate")
async def test_hvac_modes_updates_supported_features(hass: HomeAssistant) -> None:
    """Test hvac_modes updates supported features."""
    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.state == STATE_UNKNOWN
    assert state.attributes["hvac_modes"] == []
    assert state.attributes["supported_features"] == 0

    await async_trigger(
        hass,
        TEST_ATTRIBUTE_ENTITY_ID,
        "anything",
        {"hvac_modes": ["heat"]},
    )

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.state == STATE_UNKNOWN
    assert state.attributes["hvac_modes"] == [HVACMode.HEAT]
    assert state.attributes["supported_features"] == ClimateEntityFeature.TURN_ON

    await async_trigger(
        hass,
        TEST_ATTRIBUTE_ENTITY_ID,
        "anything",
        {"hvac_modes": ["off", "heat"]},
    )

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.state == STATE_UNKNOWN
    assert state.attributes["hvac_modes"] == [HVACMode.OFF, HVACMode.HEAT]
    assert (
        state.attributes["supported_features"]
        == ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
    )

    await async_trigger(
        hass,
        TEST_ATTRIBUTE_ENTITY_ID,
        "anything",
        {"hvac_modes": ["cool"]},
    )

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.state == STATE_UNKNOWN
    assert state.attributes["hvac_modes"] == [HVACMode.COOL]
    assert state.attributes["supported_features"] == ClimateEntityFeature.TURN_ON


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [
        ("fan_modes", {**SET_FAN_MODE_ACTION, **MINIMUM_REQUIREMENTS}),
        ("swing_modes", {**SET_SWING_MODE_ACTION, **MINIMUM_REQUIREMENTS}),
        (
            "swing_horizontal_modes",
            {**SET_SWING_HORIZONTAL_MODE_ACTION, **MINIMUM_REQUIREMENTS},
        ),
        (
            "preset_modes",
            {**SET_PRESET_MODE_ACTION, **MINIMUM_REQUIREMENTS},
        ),
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        ("{{ ['off', 'low', 'medium', 'high'] }}", ["off", "low", "medium", "high"]),
        ("{{ ['off', 'high'] }}", ["off", "high"]),
        ("{{ [] }}", []),
        ("{{ '[]' }}", []),
        ("{{ -3 }}", None),
        ("{{ 103.3 }}", None),
        ("{{ True }}", None),
        ("{{ False }}", None),
        ("{{ 'something' }}", None),
        ("{{ x - 1 }}", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_climate")
async def test_group_modes_template(
    hass: HomeAssistant, attribute: str, expected: Any
) -> None:
    """Test template modes for inclusive group."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.attributes.get(attribute) == expected


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [
        (
            "fan_mode",
            {
                "fan_modes": "{{ ['off', 'low', 'medium', 'high'] }}",
                **SET_FAN_MODE_ACTION,
                **MINIMUM_REQUIREMENTS,
            },
        ),
        (
            "swing_mode",
            {
                "swing_modes": "{{ ['off', 'low', 'medium', 'high'] }}",
                **SET_SWING_MODE_ACTION,
                **MINIMUM_REQUIREMENTS,
            },
        ),
        (
            "swing_horizontal_mode",
            {
                "swing_horizontal_modes": "{{ ['off', 'low', 'medium', 'high'] }}",
                **SET_SWING_HORIZONTAL_MODE_ACTION,
                **MINIMUM_REQUIREMENTS,
            },
        ),
        (
            "preset_mode",
            {
                "preset_modes": "{{ ['off', 'low', 'medium', 'high'] }}",
                **SET_PRESET_MODE_ACTION,
                **MINIMUM_REQUIREMENTS,
            },
        ),
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        ("{{ 'off' }}", "off"),
        ("{{ 'low' }}", "low"),
        ("{{ 'medium' }}", "medium"),
        ("{{ 'high' }}", "high"),
        ("{{ -3 }}", None),
        ("{{ 103.3 }}", None),
        ("{{ True }}", None),
        ("{{ False }}", None),
        ("{{ 'something' }}", None),
        ("{{ x - 1 }}", None),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_climate")
async def test_group_mode_template(
    hass: HomeAssistant, attribute: str, expected: Any
) -> None:
    """Test template mode for inclusive group."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.attributes.get(attribute) == expected


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("config", "group"),
    [
        (
            {**SET_FAN_MODE_ACTION, **MINIMUM_REQUIREMENTS},
            "fan_mode",
        ),
        (
            {
                "fan_modes": "{{ ['off', 'low', 'medium', 'high'] }}",
                **MINIMUM_REQUIREMENTS,
            },
            "fan_mode",
        ),
        (
            {**SET_SWING_MODE_ACTION, **MINIMUM_REQUIREMENTS},
            "swing_mode",
        ),
        (
            {
                "swing_modes": "{{ ['off', 'low', 'medium', 'high'] }}",
                **MINIMUM_REQUIREMENTS,
            },
            "swing_mode",
        ),
        (
            {**SET_SWING_HORIZONTAL_MODE_ACTION, **MINIMUM_REQUIREMENTS},
            "horizontal_swing_mode",
        ),
        (
            {
                "swing_horizontal_modes": "{{ ['off', 'low', 'medium', 'high'] }}",
                **MINIMUM_REQUIREMENTS,
            },
            "horizontal_swing_mode",
        ),
        (
            {**SET_PRESET_MODE_ACTION, **MINIMUM_REQUIREMENTS},
            "preset_mode",
        ),
        (
            {
                "preset_modes": "{{ ['off', 'low', 'medium', 'high'] }}",
                **MINIMUM_REQUIREMENTS,
            },
            "preset_mode",
        ),
    ],
)
async def test_bad_mode_group_config(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    group: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a bad mode group configuration."""
    platform = TEST_CLIMATE
    await setup_entity(hass, platform, style, 0, config)
    assert len(hass.states.async_all(platform.domain)) == 0
    assert (
        f"Invalid config for 'template': Some required option(s) are missing from inclusive group '{group}', expected missing options"
        in caplog.text
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("option", "option_type"),
    [
        ("max_humidity", "int"),
        ("min_humidity", "int"),
        ("max_temp", "float"),
        ("min_temp", "float"),
    ],
)
@pytest.mark.parametrize("value", ["not a number", None])
async def test_bad_min_max_options(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    option: str,
    option_type: str,
    value: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a bad min max options in configuration."""
    platform = TEST_CLIMATE
    await setup_entity(
        hass, platform, style, 0, {option: value, **MINIMUM_REQUIREMENTS}
    )
    assert len(hass.states.async_all(platform.domain)) == 0
    assert (
        f"Invalid config for 'template': expected {option_type} for dictionary value 'climate->0->{option}'"
        in caplog.text
    )


@pytest.mark.parametrize(
    "config",
    [
        {
            "target_temperature": "{{ state_attr('sensor.test_attribute', 'value') or 0.0 }}",
            **SET_TEMPERATURE_ACTION,
            **MINIMUM_REQUIREMENTS,
        }
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("extra_config", "set_attribute", "expected"),
    [
        ({"target_temperature_step": 0.1}, 7.54, 7.5),
        ({"target_temperature_step": 0.01}, 7.54, 7.5),  # Precision overrides
        ({"target_temperature_step": 1.0}, 7.54, 8),
        ({"target_temperature_step": 5.0}, 7.54, 10),
    ],
)
@pytest.mark.usefixtures("setup_climate")
async def test_target_temperature_step(
    hass: HomeAssistant, set_attribute: str, expected: Any
) -> None:
    """Test target temperature step."""
    await async_trigger(
        hass, TEST_ATTRIBUTE_ENTITY_ID, "anything", {"value": set_attribute}
    )

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.attributes.get("temperature") == expected


@pytest.mark.parametrize(
    "config",
    [
        {
            "target_humidity": "{{ state_attr('sensor.test_attribute', 'value') or 0.0 }}",
            **SET_HUMIDITY_ACTION,
            **MINIMUM_REQUIREMENTS,
        }
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("extra_config", "set_attribute", "expected"),
    [
        ({"target_humidity_step": 1}, 44, 44),
        ({"target_humidity_step": 5}, 44, 45),
        ({"target_humidity_step": 7}, 44, 42),
        ({"target_humidity_step": 10}, 44, 40),
        ({"target_humidity_step": 15}, 44, 45),
    ],
)
@pytest.mark.usefixtures("setup_climate")
async def test_target_humidity_step(
    hass: HomeAssistant, set_attribute: str, expected: Any
) -> None:
    """Test target humidity step."""
    await async_trigger(
        hass, TEST_ATTRIBUTE_ENTITY_ID, "anything", {"value": set_attribute}
    )

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.attributes.get("humidity") == expected


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("option", "option_type"),
    [
        ("target_humidity_step", "int"),
        ("target_temperature_step", "float"),
    ],
)
@pytest.mark.parametrize("value", [-1, "not a number", None])
async def test_bad_step_options(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    option: str,
    option_type: str,
    value: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a bad step options in configuration."""
    platform = TEST_CLIMATE
    await setup_entity(
        hass, platform, style, 0, {option: value, **MINIMUM_REQUIREMENTS}
    )
    assert len(hass.states.async_all(platform.domain)) == 0
    assert (
        f"Invalid config for 'template': expected {option_type} for dictionary value 'climate->0->{option}'"
        in caplog.text
    ) or (
        f"Invalid config for 'template': value must be at least 0 for dictionary value 'climate->0->{option}'"
        in caplog.text
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.5, 1.5), (0.1, 1.4), (1, 1)],
)
async def test_precision_option(
    hass: HomeAssistant, style: ConfigurationStyle, value: float, expected: float
) -> None:
    """Test precision option."""
    platform = TEST_CLIMATE
    await setup_entity(
        hass,
        platform,
        style,
        1,
        {
            "precision": value,
            "current_temperature": "{{ 1.4 }}",
            **MINIMUM_REQUIREMENTS,
        },
    )

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.attributes.get("current_temperature") == expected


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize("value", [-1, 0.0, "not a number", False, None])
async def test_bad_precision_option(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    value: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a bad precision option."""
    platform = TEST_CLIMATE
    await setup_entity(
        hass, platform, style, 0, {"precision": value, **MINIMUM_REQUIREMENTS}
    )

    assert len(hass.states.async_all(platform.domain)) == 0
    assert (
        "Invalid config for 'template': expected 0.5 or 0.1 or 1 for dictionary value 'climate->0->precision'"
        in caplog.text
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    "value",
    [UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS, UnitOfTemperature.KELVIN],
)
async def test_temperature_unit(
    hass: HomeAssistant, style: ConfigurationStyle, value: float
) -> None:
    """Test temperature_unit option."""
    platform = TEST_CLIMATE
    await setup_entity(
        hass,
        platform,
        style,
        1,
        {
            "temperature_unit": value,
            **MINIMUM_REQUIREMENTS,
        },
    )

    assert len(hass.states.async_all(platform.domain)) == 1
    assert hass.states.get(TEST_CLIMATE.entity_id)


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize("value", [-1, 0.0, "not a number", False, None])
async def test_bad_temperature_unit(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    value: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a bad temperature_unit option."""
    platform = TEST_CLIMATE
    await setup_entity(
        hass, platform, style, 0, {"temperature_unit": value, **MINIMUM_REQUIREMENTS}
    )

    assert len(hass.states.async_all(platform.domain)) == 0
    assert (
        "Invalid config for 'template': value must be one of [<UnitOfTemperature.KELVIN: 'K'>, <UnitOfTemperature.CELSIUS: '°C'>, <UnitOfTemperature.FAHRENHEIT: '°F'>] for dictionary value 'climate->0->temperature_unit'"
        in caplog.text
    )
