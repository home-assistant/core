"""The tests for the Template climate platform."""

from typing import Any

import pytest

from homeassistant.components import climate
from homeassistant.core import HomeAssistant

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
    [("current_humidity", {})],
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
    [("current_temperature", {})],
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
    """Test template humidity."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state.attributes.get("current_temperature") == expected
