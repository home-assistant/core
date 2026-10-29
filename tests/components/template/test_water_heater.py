"""The tests for the Template water heater platform."""

from enum import StrEnum
from itertools import chain
from typing import Any

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_mock_restore_state_shutdown_restart,
)
from pytest_homeassistant.typing import WebSocketGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import template, water_heater
from homeassistant.components.template.water_heater import DEFAULT_NAME
from homeassistant.components.water_heater import (
    WaterHeaterCapabilityAttribute,
    WaterHeaterStateAttribute,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.helpers.typing import ConfigType

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    assert_action,
    assert_attributes_template,
    assert_extra_template_attributes,
    assert_invalid_config_entry_actions_do_not_create_entities,
    assert_invalid_yaml_actions_do_not_create_entities,
    assert_state_and_attributes,
    async_get_flow_preview_state,
    async_trigger,
    make_test_action,
    make_test_trigger,
    setup_and_test_nested_unique_id,
    setup_and_test_unique_id,
    setup_entity,
    setup_mock_template_entity_restore_state,
    setup_restore_template_entity,
)

TEST_STATE_ENTITY_ID = "sensor.test_state"
TEST_ATTRIBUTE_ENTITY_ID = "sensor.test_attribute"
TEST_AVAILABILITY_ENTITY = "binary_sensor.availability"

TEST_WATER_HEATER = TemplatePlatformSetup(
    water_heater.DOMAIN,
    "test_water_heater",
    make_test_trigger(
        TEST_STATE_ENTITY_ID,
        TEST_AVAILABILITY_ENTITY,
        TEST_ATTRIBUTE_ENTITY_ID,
    ),
)

SET_OPERATION_MODE_ACTION = make_test_action(
    "set_operation_mode",
    {
        "operation_mode": "{{ operation_mode }}",
    },
)
SET_TEMPERATURE_ACTION = make_test_action(
    "set_temperature",
    {
        "temperature": "{{ temperature }}",
        "operation_mode": "{{ operation_mode }}",
    },
)
TURN_AWAY_MODE_ON_ACTION = make_test_action("turn_away_mode_on")
TURN_AWAY_MODE_OFF_ACTION = make_test_action("turn_away_mode_off")
TURN_ON_ACTION = make_test_action("turn_on")
TURN_OFF_ACTION = make_test_action("turn_off")

OPERATION_LIST = {
    "operation_list": "{{ ['off', 'eco', 'electric', 'gas'] }}",
}
EXPECTED_OPERATION_LIST = ["off", "eco", "electric", "gas"]
MINIMUM_REQUIREMENTS = {
    **OPERATION_LIST,
    **SET_OPERATION_MODE_ACTION,
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
        water_heater.DOMAIN,
        service,
        {**(service_data or {}), ATTR_ENTITY_ID: TEST_WATER_HEATER.entity_id},
        blocking=True,
    )
    assert_action(
        TEST_WATER_HEATER, calls, current + 1, expected_action, **(expected_data or {})
    )


@pytest.fixture
async def setup_base_water_heater(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: dict[str, Any],
) -> None:
    """Do setup of water heater integration."""
    await setup_entity(hass, TEST_WATER_HEATER, style, count, config)


@pytest.fixture
async def setup_water_heater(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: dict[str, Any],
    extra_config: dict[str, Any],
) -> None:
    """Do setup of water heater integration."""
    await setup_entity(
        hass, TEST_WATER_HEATER, style, 1, config, extra_config=extra_config
    )


@pytest.fixture
async def setup_single_attribute_water_heater(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    attribute: str,
    attribute_template: str,
    extra_config: dict,
) -> None:
    """Do setup of water heater integration."""
    await setup_entity(
        hass,
        TEST_WATER_HEATER,
        style,
        1,
        {attribute: attribute_template} if attribute and attribute_template else {},
        extra_config=extra_config,
    )


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
@pytest.mark.usefixtures("setup_single_attribute_water_heater")
async def test_temperature_template(hass: HomeAssistant, expected: Any) -> None:
    """Test template current_temperature."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state.attributes.get("current_temperature") == expected


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [("operation_list", SET_OPERATION_MODE_ACTION)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        (
            "{{ ['off', 'eco', 'electric'] }}",
            ["off", "eco", "electric"],
        ),
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
@pytest.mark.usefixtures("setup_single_attribute_water_heater")
async def test_operation_list_template(hass: HomeAssistant, expected: Any) -> None:
    """Test operation_list template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state.attributes.get("operation_list") == expected


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [("operation_mode", MINIMUM_REQUIREMENTS)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("attribute_template", "expected"),
    [
        ("{{ 'off' }}", "off"),
        ("{{ 'eco' }}", "eco"),
        ("{{ 'electric' }}", "electric"),
        ("{{ 'gas' }}", "gas"),
        ("{{ 'not_valid' }}", STATE_UNKNOWN),
        ("{{ -3 }}", STATE_UNKNOWN),
        ("{{ 103.3 }}", STATE_UNKNOWN),
        ("{{ True }}", STATE_UNKNOWN),
        ("{{ False }}", STATE_UNKNOWN),
        ("{{ x - 1 }}", STATE_UNAVAILABLE),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_water_heater")
async def test_operation_mode_template(hass: HomeAssistant, expected: Any) -> None:
    """Test operation_mode template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state.state == expected


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("config", "option"),
    [
        (
            SET_OPERATION_MODE_ACTION,
            "operation_list",
        ),
        (
            OPERATION_LIST,
            "set_operation_mode",
        ),
    ],
)
async def test_missing_required_operation_mode_option(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    option: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a water heater missing a required operation mode option."""
    platform = TEST_WATER_HEATER
    await setup_entity(hass, platform, style, 0, config)
    assert len(hass.states.async_all(platform.domain)) == 0
    assert (
        f"Invalid config for 'template': required key '{option}' not provided"
        in caplog.text
    )


@pytest.mark.parametrize(("config", "extra_config"), [(MINIMUM_REQUIREMENTS, {})])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_water_heater")
async def test_set_operation_mode_action(
    hass: HomeAssistant,
    calls: list[ServiceCall],
) -> None:
    """Test setting valid operation mode via action."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state is not None

    await _call_and_assert_action(
        hass,
        calls,
        "set_operation_mode",
        {"operation_mode": "eco"},
        {"operation_mode": "eco"},
        "set_operation_mode",
    )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            water_heater.DOMAIN,
            "set_operation_mode",
            {
                "operation_mode": "not_valid",
                ATTR_ENTITY_ID: TEST_WATER_HEATER.entity_id,
            },
            blocking=True,
        )


@pytest.mark.parametrize(("config", "extra_config"), [(MINIMUM_REQUIREMENTS, {})])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_water_heater")
async def test_optimistic_set_operation_mode_action(
    hass: HomeAssistant,
    calls: list[ServiceCall],
) -> None:
    """Test optimistic set_operation_mode action."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state is not None

    await _call_and_assert_action(
        hass,
        calls,
        "set_operation_mode",
        {"operation_mode": "eco"},
        {"operation_mode": "eco"},
        "set_operation_mode",
    )

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state is not None
    assert state.state == "eco"

    await _call_and_assert_action(
        hass,
        calls,
        "set_operation_mode",
        {"operation_mode": "electric"},
        {"operation_mode": "electric"},
        "set_operation_mode",
    )

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state is not None
    assert state.state == "electric"


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [
        (
            "target_temperature",
            {
                "min_temperature": -2,
                "max_temperature": 101,
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
@pytest.mark.usefixtures("setup_single_attribute_water_heater")
async def test_target_temperature_template(hass: HomeAssistant, expected: Any) -> None:
    """Test template target_temperature."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state.attributes.get("temperature") == expected


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    "config",
    [
        {"target_temperature": 32, **MINIMUM_REQUIREMENTS},
    ],
)
async def test_missing_set_temperature_config(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a bad target temperature configuration."""
    platform = TEST_WATER_HEATER
    await setup_entity(hass, platform, style, 0, config)
    assert len(hass.states.async_all(platform.domain)) == 0
    assert (
        "Invalid config for 'template': Required option: 'set_temperature' is missing for option"
        in caplog.text
    )


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_set_temperature_action_with_operation_mode(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    calls: list[ServiceCall],
) -> None:
    """Test set_temperature action with operation_mode."""
    await setup_entity(
        hass,
        TEST_WATER_HEATER,
        style,
        1,
        {
            "operation_mode": "{{ 'eco' }}",
            "target_temperature": "{{ 21 }}",
            "min_temperature": -2,
            "max_temperature": 101,
            **MINIMUM_REQUIREMENTS,
            **SET_TEMPERATURE_ACTION,
        },
    )

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state is not None

    await hass.services.async_call(
        water_heater.DOMAIN,
        "set_temperature",
        {
            "operation_mode": "electric",
            "temperature": 18,
            ATTR_ENTITY_ID: TEST_WATER_HEATER.entity_id,
        },
        blocking=True,
    )
    assert_action(
        TEST_WATER_HEATER, calls, 2, "set_operation_mode", 0, operation_mode="electric"
    )
    assert_action(
        TEST_WATER_HEATER,
        calls,
        2,
        "set_temperature",
        operation_mode="electric",
        temperature=18,
    )

    assert_state_and_attributes(hass, TEST_WATER_HEATER, "eco", {"temperature": 21})


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_set_temperature_action_with_invalid_operation_mode(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    calls: list[ServiceCall],
) -> None:
    """Test set_temperature action rejects an operation_mode not in operation_list."""
    await setup_entity(
        hass,
        TEST_WATER_HEATER,
        style,
        1,
        {
            "operation_mode": "{{ 'eco' }}",
            "target_temperature": "{{ 21 }}",
            "min_temperature": -2,
            "max_temperature": 101,
            **MINIMUM_REQUIREMENTS,
            **SET_TEMPERATURE_ACTION,
        },
    )

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state is not None

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            water_heater.DOMAIN,
            "set_temperature",
            {
                "operation_mode": "not_valid",
                "temperature": 18,
                ATTR_ENTITY_ID: TEST_WATER_HEATER.entity_id,
            },
            blocking=True,
        )

    assert len(calls) == 0


@pytest.mark.parametrize(
    ("config", "extra_config"), [(MINIMUM_REQUIREMENTS, SET_TEMPERATURE_ACTION)]
)
@pytest.mark.parametrize(
    (
        "action_variables",
        "expected_variables",
        "expected_attributes",
    ),
    [
        (
            {"temperature": 50},
            {"temperature": 50},
            {"temperature": 50},
        ),
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_water_heater")
async def test_optimistic_set_temperature_action(
    hass: HomeAssistant,
    action_variables: ConfigType,
    expected_variables: ConfigType,
    expected_attributes: ConfigType,
    calls: list[ServiceCall],
) -> None:
    """Test optimistic set_temperature action."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    assert_state_and_attributes(
        hass,
        TEST_WATER_HEATER,
        STATE_UNKNOWN,
        {"temperature": None},
    )

    await hass.services.async_call(
        water_heater.DOMAIN,
        "set_temperature",
        {
            **action_variables,
            ATTR_ENTITY_ID: TEST_WATER_HEATER.entity_id,
        },
        blocking=True,
    )
    assert_action(
        TEST_WATER_HEATER,
        calls,
        1,
        "set_temperature",
        **expected_variables,
    )

    assert_state_and_attributes(
        hass, TEST_WATER_HEATER, STATE_UNKNOWN, expected_attributes
    )


@pytest.mark.parametrize(
    "config",
    [
        {
            "target_temperature": "{{ state_attr('sensor.test_attribute', 'value') or 0.0 }}",
            "min_temperature": -2,
            "max_temperature": 101,
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
        ({"target_temperature_step": 1.0}, 7.54, 8),
        ({"target_temperature_step": 5.0}, 7.54, 10),
    ],
)
@pytest.mark.usefixtures("setup_water_heater")
async def test_target_temperature_step(
    hass: HomeAssistant, set_attribute: float, expected: float
) -> None:
    """Test target temperature step."""
    await async_trigger(
        hass, TEST_ATTRIBUTE_ENTITY_ID, "anything", {"value": set_attribute}
    )

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state.attributes.get("temperature") == expected


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("option", "option_type"),
    [
        ("max_temperature", "float"),
        ("min_temperature", "float"),
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
    platform = TEST_WATER_HEATER
    await setup_entity(
        hass, platform, style, 0, {option: value, **MINIMUM_REQUIREMENTS}
    )
    assert len(hass.states.async_all(platform.domain)) == 0
    assert (
        f"Invalid config for 'template': expected {option_type} for dictionary value 'water_heater->0->{option}'"
        in caplog.text
    )


@pytest.mark.parametrize(
    ("attribute", "extra_config"),
    [
        (
            "away_mode",
            {
                **TURN_AWAY_MODE_ON_ACTION,
                **TURN_AWAY_MODE_OFF_ACTION,
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
        ("{{ true }}", STATE_ON),
        ("{{ false }}", STATE_OFF),
        ("{{ 'something' }}", STATE_OFF),
        ("{{ x - 1 }}", STATE_OFF),
    ],
)
@pytest.mark.usefixtures("setup_single_attribute_water_heater")
async def test_away_mode_template(hass: HomeAssistant, expected: Any) -> None:
    """Test template away_mode."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state.attributes.get("away_mode") == expected


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    "config",
    [
        {**TURN_AWAY_MODE_ON_ACTION, **MINIMUM_REQUIREMENTS},
        {**TURN_AWAY_MODE_OFF_ACTION, **MINIMUM_REQUIREMENTS},
    ],
)
async def test_bad_away_mode_actions_config(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a bad away mode actions configuration."""
    platform = TEST_WATER_HEATER
    await setup_entity(hass, platform, style, 0, config)
    assert len(hass.states.async_all(platform.domain)) == 0
    assert "some but not all values in the same group of inclusion" in caplog.text


@pytest.mark.parametrize(
    ("config", "extra_config"),
    [(MINIMUM_REQUIREMENTS, {**TURN_AWAY_MODE_ON_ACTION, **TURN_AWAY_MODE_OFF_ACTION})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_water_heater")
async def test_optimistic_away_mode_actions(
    hass: HomeAssistant,
    calls: list[ServiceCall],
) -> None:
    """Test optimistic away mode actions."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state is not None
    assert state.attributes.get("away_mode") == STATE_OFF

    await _call_and_assert_action(
        hass,
        calls,
        "set_away_mode",
        {"away_mode": True},
        {},
        "turn_away_mode_on",
    )

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state.attributes.get("away_mode") == STATE_ON

    await _call_and_assert_action(
        hass,
        calls,
        "set_away_mode",
        {"away_mode": False},
        {},
        "turn_away_mode_off",
    )

    state = hass.states.get(TEST_WATER_HEATER.entity_id)
    assert state.attributes.get("away_mode") == STATE_OFF


@pytest.mark.parametrize(
    ("config", "extra_config"),
    [
        (
            {**TURN_ON_ACTION, **TURN_OFF_ACTION, **MINIMUM_REQUIREMENTS},
            {},
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_water_heater")
async def test_turn_on_off_actions(
    hass: HomeAssistant,
    calls: list[ServiceCall],
) -> None:
    """Test turn_on and turn_off actions."""

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    await _call_and_assert_action(hass, calls, "turn_on")
    await _call_and_assert_action(hass, calls, "turn_off")


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    "config",
    [
        {**TURN_ON_ACTION, **MINIMUM_REQUIREMENTS},
        {**TURN_OFF_ACTION, **MINIMUM_REQUIREMENTS},
    ],
)
async def test_bad_on_off_actions_config(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a bad on/off actions configuration."""
    platform = TEST_WATER_HEATER
    await setup_entity(hass, platform, style, 0, config)
    assert len(hass.states.async_all(platform.domain)) == 0
    assert "some but not all values in the same group of inclusion" in caplog.text


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    "value", [UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT]
)
async def test_temperature_unit(
    hass: HomeAssistant, style: ConfigurationStyle, value: str
) -> None:
    """Test temperature_unit option."""
    platform = TEST_WATER_HEATER
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
    assert hass.states.get(TEST_WATER_HEATER.entity_id)


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize("value", [-1, 0.0, "not a number", False, None])
async def test_bad_temperature_unit(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    value: Any,
) -> None:
    """Test a bad temperature_unit option."""
    platform = TEST_WATER_HEATER
    await setup_entity(
        hass, platform, style, 0, {"temperature_unit": value, **MINIMUM_REQUIREMENTS}
    )

    assert len(hass.states.async_all(platform.domain)) == 0


@pytest.mark.parametrize(
    ("extra_config", "attribute_template"),
    [
        (
            {
                "operation_mode": "{{ states('sensor.test_state') }}",
                **MINIMUM_REQUIREMENTS,
            },
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
@pytest.mark.usefixtures("setup_single_attribute_water_heater")
async def test_available_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability templates with values from other entities."""
    hass.states.async_set(TEST_AVAILABILITY_ENTITY, STATE_ON)
    await hass.async_block_till_done()

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "eco")

    assert hass.states.get(TEST_WATER_HEATER.entity_id).state != STATE_UNAVAILABLE

    hass.states.async_set(TEST_AVAILABILITY_ENTITY, STATE_OFF)
    await hass.async_block_till_done()

    await async_trigger(hass, TEST_STATE_ENTITY_ID, "electric")

    assert hass.states.get(TEST_WATER_HEATER.entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("extra_config", "attribute_template"),
    [
        (
            {
                "operation_mode": "{{ states('sensor.test_state') }}",
                **MINIMUM_REQUIREMENTS,
            },
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
@pytest.mark.usefixtures("setup_single_attribute_water_heater")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog_setup_text: str
) -> None:
    """Test that an invalid availability keeps the device available."""
    assert hass.states.get(TEST_WATER_HEATER.entity_id).state != STATE_UNAVAILABLE
    assert "UndefinedError: 'x' is undefined" in caplog_setup_text


@pytest.mark.parametrize("config", [MINIMUM_REQUIREMENTS])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_unique_id(
    hass: HomeAssistant, style: ConfigurationStyle, config: ConfigType
) -> None:
    """Test unique_id option only creates one entity per id."""
    await setup_and_test_unique_id(hass, TEST_WATER_HEATER, style, config)


@pytest.mark.parametrize("config", [MINIMUM_REQUIREMENTS])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_nested_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a template unique_id propagates to entity unique_ids."""
    await setup_and_test_nested_unique_id(
        hass, TEST_WATER_HEATER, style, entity_registry, config
    )


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests creating a entity from a config entry."""

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "operation_mode": "{{ 'eco' }}",
            **MINIMUM_REQUIREMENTS,
            "template_type": water_heater.DOMAIN,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("water_heater.my_template")
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
        water_heater.DOMAIN,
        {
            "name": "My template",
            "operation_mode": "{{ 'eco' }}",
            **MINIMUM_REQUIREMENTS,
        },
    )

    assert state["state"] == "eco"


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
            "eco",
            {
                "current_operation": "eco",
                "current_temperature": 35.0,
                "is_away_mode_on": False,
                "operation_list": ["eco"],
                "target_temperature": None,
            },
            "eco",
            {
                "current_temperature": 35.0,
                "away_mode": STATE_OFF,
                "operation_list": ["eco"],
                "temperature": None,
            },
        ),
        (
            STATE_UNAVAILABLE,
            {
                "current_operation": "eco",
                "current_temperature": 35.0,
                "is_away_mode_on": False,
                "operation_list": ["eco"],
                "target_temperature": None,
            },
            STATE_UNKNOWN,
            {},
        ),
        (
            STATE_UNKNOWN,
            {
                "current_operation": None,
                "current_temperature": 35.0,
                "is_away_mode_on": False,
                "operation_list": ["eco"],
                "target_temperature": None,
            },
            STATE_UNKNOWN,
            {},
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
    """Test restoring trigger template water heater."""

    restored_attributes = {  # These should be ignored
        "current_position": 5,
        "current_tilt_position": 5,
    }

    setup_mock_template_entity_restore_state(
        hass,
        TEST_WATER_HEATER,
        saved_state,
        saved_extra_data=saved_extra_data,
        saved_attributes=restored_attributes,
    )

    await setup_restore_template_entity(
        hass,
        TEST_WATER_HEATER,
        style,
        {
            "current_temperature": "{{ state_attr('sensor.test_state', 'current_temperature') }}",
            "operation_mode": "{{ state_attr('sensor.test_state', 'operation_mode') }}",
            "operation_list": "{{ state_attr('sensor.test_state', 'operation_list') or [] }}",
            "set_operation_mode": [],
            "target_temperature": "{{ state_attr('sensor.test_state', 'target_temperature') }}",
            "set_temperature": [],
            **TURN_AWAY_MODE_ON_ACTION,
            **TURN_AWAY_MODE_OFF_ACTION,
        },
        "is_state_attr('sensor.test_state', 'operation_mode', 'eco')",
    )

    assert_state_and_attributes(
        hass,
        TEST_WATER_HEATER,
        initial_state,
        initial_attributes,
    )

    await async_trigger(hass, "sensor.test_state", "x", {"operation_list": ["eco"]})
    await async_trigger(
        hass,
        "sensor.test_state",
        "x",
        {"operation_list": ["eco"], "operation_mode": "eco"},
    )

    assert_state_and_attributes(hass, TEST_WATER_HEATER, "eco")


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
        TEST_WATER_HEATER,
        style,
        1,
        config={
            "operation_mode": "{{ state_attr('sensor.test_state', 'operation_mode') }}",
            **MINIMUM_REQUIREMENTS,
        },
    )

    await async_trigger(
        hass,
        TEST_STATE_ENTITY_ID,
        "anything",
        {"operation_mode": "eco"},
    )

    assert_state_and_attributes(
        hass, TEST_WATER_HEATER, "eco", {"operation_list": EXPECTED_OPERATION_LIST}
    )

    await async_mock_restore_state_shutdown_restart(hass)

    assert len(hass_storage[RESTORE_STATE_KEY]["data"]) == 1
    state = hass_storage[RESTORE_STATE_KEY]["data"][0]["state"]
    assert state["entity_id"] == TEST_WATER_HEATER.entity_id

    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]
    assert extra_data == {
        "current_operation": "eco",
        "current_temperature": None,
        "is_away_mode_on": None,
        "operation_list": EXPECTED_OPERATION_LIST,
        "target_temperature": None,
    }


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
@pytest.mark.parametrize(
    ("action", "config"),
    [
        ("set_operation_mode", OPERATION_LIST),
        ("set_temperature", MINIMUM_REQUIREMENTS),
        (
            "turn_away_mode_on",
            {**TURN_AWAY_MODE_OFF_ACTION, **MINIMUM_REQUIREMENTS},
        ),
        (
            "turn_away_mode_off",
            {**TURN_AWAY_MODE_ON_ACTION, **MINIMUM_REQUIREMENTS},
        ),
        ("turn_on", {**TURN_OFF_ACTION, **MINIMUM_REQUIREMENTS}),
        ("turn_off", {**TURN_ON_ACTION, **MINIMUM_REQUIREMENTS}),
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
        hass, TEST_WATER_HEATER, style, config, action, caplog
    )


@pytest.mark.parametrize(
    ("action", "config"),
    [
        ("set_operation_mode", OPERATION_LIST),
        ("set_temperature", MINIMUM_REQUIREMENTS),
        (
            "turn_away_mode_on",
            {**TURN_AWAY_MODE_OFF_ACTION, **MINIMUM_REQUIREMENTS},
        ),
        (
            "turn_away_mode_off",
            {**TURN_AWAY_MODE_ON_ACTION, **MINIMUM_REQUIREMENTS},
        ),
        ("turn_on", {**TURN_OFF_ACTION, **MINIMUM_REQUIREMENTS}),
        ("turn_off", {**TURN_ON_ACTION, **MINIMUM_REQUIREMENTS}),
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
        hass, TEST_WATER_HEATER, config, action, caplog
    )


@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_extra_template_attributes(
    hass: HomeAssistant, style: ConfigurationStyle
) -> None:
    """Test extra attributes."""
    await assert_extra_template_attributes(
        hass, TEST_WATER_HEATER, style, MINIMUM_REQUIREMENTS
    )


@pytest.mark.parametrize(
    "attribute",
    list(chain(WaterHeaterCapabilityAttribute, WaterHeaterStateAttribute)),
)
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_blocked_template_attributes(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    attribute: StrEnum,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test blocked extra attributes."""
    await setup_entity(
        hass,
        TEST_WATER_HEATER,
        style,
        0,
        {
            **MINIMUM_REQUIREMENTS,
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
        TEST_WATER_HEATER,
        style,
        MINIMUM_REQUIREMENTS,
        caplog,
    )


@pytest.mark.parametrize(
    "attribute",
    list(chain(WaterHeaterCapabilityAttribute, WaterHeaterStateAttribute)),
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
        TEST_WATER_HEATER,
        style,
        1,
        {
            **MINIMUM_REQUIREMENTS,
            "attributes": f"{{{{ dict({attribute}='does not matter') }}}}",
        },
    )

    await async_trigger(hass, "sensor.test_extra_attributes", "anything")

    error = (
        f"Unsupported attribute(s) found for {TEST_WATER_HEATER.entity_id}: {attribute}"
    )
    assert error in caplog.text
