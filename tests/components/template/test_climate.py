"""Tests for the template climate platform."""

import pytest

from homeassistant.components import climate
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    HVACMode,
)
from homeassistant.components.template.climate import (
    CONF_PRESETS_FEATURES,
    TemplateClimateEntityPresetFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    PRECISION_WHOLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, HomeAssistant, ServiceCall, State
from homeassistant.helpers.typing import ConfigType

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    assert_action,
    async_trigger,
    make_test_action,
    make_test_trigger,
    setup_entity,
)

from tests.common import mock_component, mock_restore_cache

TEST_STATE_ENTITY_ID = "sensor.test_climate_state"
TEST_CLIMATE = TemplatePlatformSetup(
    climate.DOMAIN,
    "test_template_climate",
    make_test_trigger(TEST_STATE_ENTITY_ID),
)

SET_HVAC_MODE_ACTION = make_test_action(
    "set_hvac_mode", {ATTR_HVAC_MODE: "{{ hvac_mode }}"}
)
SET_TEMPERATURE_ACTION = make_test_action(
    "set_temperature",
    {
        ATTR_TEMPERATURE: "{{ temperature }}",
        ATTR_TARGET_TEMP_LOW: "{{ target_temp_low | default(None) }}",
        ATTR_TARGET_TEMP_HIGH: "{{ target_temp_high | default(None) }}",
        ATTR_HVAC_MODE: "{{ hvac_mode | default(None) }}",
    },
)


@pytest.fixture
async def setup_climate(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: ConfigType,
) -> None:
    """Set up a climate entity."""
    await setup_entity(hass, TEST_CLIMATE, style, count, config)


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "hvac_mode_template": "{{ states('sensor.test_climate_state') }}",
                "hvac_modes": [HVACMode.OFF, HVACMode.HEAT],
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("source_state", "expected_state"),
    [
        (HVACMode.OFF, HVACMode.OFF),
        (HVACMode.HEAT, HVACMode.HEAT),
        ("bogus", STATE_UNKNOWN),
    ],
)
@pytest.mark.usefixtures("setup_climate")
async def test_hvac_mode_template(
    hass: HomeAssistant,
    source_state: str,
    expected_state: str,
) -> None:
    """Test the HVAC mode template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, source_state)

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "hvac_modes": [HVACMode.OFF, HVACMode.HEAT],
                **SET_HVAC_MODE_ACTION,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_climate")
async def test_set_hvac_mode_action(
    hass: HomeAssistant,
    calls: list[ServiceCall],
) -> None:
    """Test setting the HVAC mode runs the configured action."""
    await hass.services.async_call(
        climate.DOMAIN,
        climate.SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: TEST_CLIMATE.entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert_action(
        TEST_CLIMATE,
        calls,
        1,
        "set_hvac_mode",
        hvac_mode=HVACMode.HEAT,
    )


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "hvac_modes": [HVACMode.OFF, HVACMode.HEAT],
                **SET_HVAC_MODE_ACTION,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_climate")
async def test_turn_on_off_uses_last_hvac_mode(
    hass: HomeAssistant,
    calls: list[ServiceCall],
) -> None:
    """Test turn on/off reuses the last non-off HVAC mode."""
    await hass.services.async_call(
        climate.DOMAIN,
        climate.SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: TEST_CLIMATE.entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.services.async_call(
        climate.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_CLIMATE.entity_id},
        blocking=True,
    )
    await hass.services.async_call(
        climate.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_CLIMATE.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT

    assert_action(
        TEST_CLIMATE, calls, 3, "set_hvac_mode", index=0, hvac_mode=HVACMode.HEAT
    )
    assert_action(
        TEST_CLIMATE, calls, 3, "set_hvac_mode", index=1, hvac_mode=HVACMode.OFF
    )
    assert_action(
        TEST_CLIMATE, calls, 3, "set_hvac_mode", index=2, hvac_mode=HVACMode.HEAT
    )


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "hvac_modes": [HVACMode.OFF, HVACMode.HEAT, HVACMode.HEAT_COOL],
                "temp_step": 0.5,
                **SET_TEMPERATURE_ACTION,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_climate")
async def test_set_temperature_action(
    hass: HomeAssistant,
    calls: list[ServiceCall],
) -> None:
    """Test setting target temperatures runs the configured action."""
    await hass.services.async_call(
        climate.DOMAIN,
        climate.SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: TEST_CLIMATE.entity_id,
            ATTR_TEMPERATURE: 20.3,
            ATTR_TARGET_TEMP_LOW: 18.2,
            ATTR_TARGET_TEMP_HIGH: 22.6,
            ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
        },
        blocking=True,
    )

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT_COOL
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 18.0
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 22.5

    assert_action(
        TEST_CLIMATE,
        calls,
        1,
        "set_temperature",
        temperature=20.5,
        target_temp_low=18.0,
        target_temp_high=22.5,
        hvac_mode=HVACMode.HEAT_COOL,
    )


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "hvac_modes": [HVACMode.OFF, HVACMode.HEAT, HVACMode.HEAT_COOL],
                "temp_step": 0.5,
                "precision": PRECISION_WHOLE,
                **SET_TEMPERATURE_ACTION,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_climate")
async def test_set_temperature_action_with_explicit_precision(
    hass: HomeAssistant,
    calls: list[ServiceCall],
) -> None:
    """Test explicit precision affects displayed state temperature values."""
    await hass.services.async_call(
        climate.DOMAIN,
        climate.SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: TEST_CLIMATE.entity_id,
            ATTR_TARGET_TEMP_LOW: 18.2,
            ATTR_TARGET_TEMP_HIGH: 22.6,
            ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
        },
        blocking=True,
    )

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT_COOL
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 22

    assert_action(
        TEST_CLIMATE,
        calls,
        1,
        "set_temperature",
        target_temp_low=18.0,
        target_temp_high=22.5,
        hvac_mode=HVACMode.HEAT_COOL,
    )


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_restore_turn_on_off_with_string_hvac_mode_attributes(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    calls: list[ServiceCall],
) -> None:
    """Test restoring last_on_mode/off_mode with string values works."""
    mock_restore_cache(
        hass,
        (
            State(
                TEST_CLIMATE.entity_id,
                HVACMode.OFF,
                {
                    "last_on_mode": {"hvac_mode": HVACMode.HEAT.value},
                    "off_mode": {"hvac_mode": HVACMode.OFF.value},
                },
            ),
        ),
    )

    hass.set_state(CoreState.starting)
    mock_component(hass, "recorder")

    await setup_entity(
        hass,
        TEST_CLIMATE,
        style,
        1,
        {"hvac_modes": [HVACMode.OFF, HVACMode.HEAT], **SET_HVAC_MODE_ACTION},
    )

    await hass.services.async_call(
        climate.DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_CLIMATE.entity_id},
        blocking=True,
    )
    await hass.services.async_call(
        climate.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_CLIMATE.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state is not None
    assert state.state == HVACMode.OFF

    assert_action(
        TEST_CLIMATE, calls, 2, "set_hvac_mode", index=0, hvac_mode=HVACMode.HEAT
    )
    assert_action(
        TEST_CLIMATE, calls, 2, "set_hvac_mode", index=1, hvac_mode=HVACMode.OFF
    )


@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_apply_preset_with_hvac_mode_only_uses_set_hvac_mode_action(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    calls: list[ServiceCall],
) -> None:
    """Test hvac-only presets route through set_hvac_mode, not set_temperature."""
    mock_restore_cache(
        hass,
        (
            State(
                TEST_CLIMATE.entity_id,
                HVACMode.OFF,
                {
                    "presets": {"eco": {"hvac_mode": HVACMode.HEAT.value}},
                },
            ),
        ),
    )

    hass.set_state(CoreState.starting)
    mock_component(hass, "recorder")

    await setup_entity(
        hass,
        TEST_CLIMATE,
        style,
        1,
        {
            "hvac_modes": [HVACMode.OFF, HVACMode.HEAT],
            "preset_modes": ["eco"],
            CONF_PRESETS_FEATURES: TemplateClimateEntityPresetFeature.HVAC_MODE,
            **SET_HVAC_MODE_ACTION,
            **SET_TEMPERATURE_ACTION,
        },
    )

    await hass.services.async_call(
        climate.DOMAIN,
        climate.SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: TEST_CLIMATE.entity_id, ATTR_PRESET_MODE: "eco"},
        blocking=True,
    )

    state = hass.states.get(TEST_CLIMATE.entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT

    assert_action(TEST_CLIMATE, calls, 1, "set_hvac_mode", hvac_mode=HVACMode.HEAT)
