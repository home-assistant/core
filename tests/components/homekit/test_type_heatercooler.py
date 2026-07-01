"""Test different accessory types: HeaterCooler."""

from unittest.mock import patch

import pytest

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.homekit.accessories import HomeDriver
from homeassistant.components.homekit.const import (
    CHAR_ACTIVE,
    CHAR_COOLING_THRESHOLD_TEMPERATURE,
    CHAR_HEATING_THRESHOLD_TEMPERATURE,
    CHAR_ROTATION_SPEED,
    CHAR_SWING_MODE,
    CHAR_TARGET_HEATER_COOLER_STATE,
    PROP_MAX_VALUE,
    PROP_MIN_STEP,
    PROP_MIN_VALUE,
)
from homeassistant.components.homekit.type_heatercooler import (
    HC_COOLING,
    HC_HEATING,
    HC_IDLE,
    HC_INACTIVE,
    HC_TARGET_AUTO,
    HC_TARGET_COOL,
    HC_TARGET_HEAT,
    HeaterCooler,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import async_mock_service


async def test_heatercooler_basic(hass: HomeAssistant, hk_driver: HomeDriver) -> None:
    """Test basic HeaterCooler functionality."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.OFF],
        ATTR_MIN_TEMP: 10.0,
        ATTR_MAX_TEMP: 30.0,
        ATTR_TEMPERATURE: 20.0,
        ATTR_CURRENT_TEMPERATURE: 18.0,
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 1
    assert acc.category == 9  # Thermostat

    # Check initial state (OFF)
    assert acc.char_active.value == 0
    assert acc.char_current_state.value == HC_INACTIVE  # OFF reports Inactive
    assert acc.char_target_state.value == HC_TARGET_AUTO
    assert acc.char_current_temp.value == 18.0
    assert acc.char_cool.value == 20.0
    assert acc.char_heat.value == 20.0

    # Check temperature properties
    assert acc.char_cool.properties[PROP_MIN_VALUE] == 10.0
    assert acc.char_cool.properties[PROP_MAX_VALUE] == 30.0
    assert acc.char_heat.properties[PROP_MIN_VALUE] == 10.0
    assert acc.char_heat.properties[PROP_MAX_VALUE] == 30.0

    # The mode and range attributes must trigger an accessory reload so the
    # characteristic set stays in sync with the device.
    assert set(acc._reload_on_change_attrs) >= {
        ATTR_MIN_TEMP,
        ATTR_MAX_TEMP,
        ATTR_FAN_MODES,
        ATTR_SWING_MODES,
        ATTR_HVAC_MODES,
    }


async def test_heatercooler_with_fan_and_swing(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test HeaterCooler with fan and swing mode support."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.OFF],
        ATTR_FAN_MODES: [FAN_LOW, FAN_MIDDLE, FAN_MEDIUM, FAN_HIGH],
        ATTR_SWING_MODES: ["off", "vertical", "horizontal", "both"],
        ATTR_FAN_MODE: FAN_LOW,
        ATTR_SWING_MODE: "off",
        ATTR_TEMPERATURE: 22.0,
        ATTR_CURRENT_TEMPERATURE: 20.0,
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Check that fan and swing characteristics are present
    assert hasattr(acc, "char_speed")
    assert hasattr(acc, "char_swing")
    assert acc.char_speed.value == 25  # FAN_LOW maps to 25% (index 0 of 4 speeds)
    assert acc.char_swing.value == 0  # off


async def test_heatercooler_modes_auto_preferred(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test HeaterCooler mode mapping when AUTO mode is available."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.OFF],
    }

    hass.states.async_set(entity_id, HVACMode.AUTO, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # AUTO mode should be preferred for HC_TARGET_AUTO
    assert acc._hk_to_ha_target[HC_TARGET_AUTO] == HVACMode.AUTO


async def test_heatercooler_modes_heat_cool_fallback(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test HeaterCooler mode mapping when HEAT_COOL mode is available but not AUTO."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.HEAT_COOL,
            HVACMode.OFF,
        ],
    }

    hass.states.async_set(entity_id, HVACMode.HEAT_COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # HEAT_COOL mode should be used for HC_TARGET_AUTO when AUTO is not available
    assert acc._hk_to_ha_target[HC_TARGET_AUTO] == HVACMode.HEAT_COOL


async def test_heatercooler_modes_heat_cool_only_no_auto(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test that Auto is not offered for entities without a range mode."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
    }

    hass.states.async_set(entity_id, HVACMode.HEAT, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Auto has no backing mode, so it must not be mapped or offered to HomeKit
    assert HC_TARGET_AUTO not in acc._hk_to_ha_target
    assert (
        HC_TARGET_AUTO not in acc.char_target_state.properties["ValidValues"].values()
    )
    assert acc.char_target_state.value == HC_TARGET_HEAT


async def test_heatercooler_cooling_only_no_heat_target(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test a cooling-only entity does not expose the Heat target."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.COOL, HVACMode.OFF],
        ATTR_FAN_MODES: ["low", "high"],
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Heat has no backing mode, so HomeKit must not offer it
    assert HC_TARGET_HEAT not in acc._hk_to_ha_target
    valid_values = acc.char_target_state.properties["ValidValues"].values()
    assert HC_TARGET_HEAT not in valid_values
    assert HC_TARGET_AUTO not in valid_values
    assert acc.char_target_state.value == HC_TARGET_COOL


async def test_heatercooler_temperature_step(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test HeaterCooler relies on the HomeKit default temperature step."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # No explicit min step so HomeKit keeps its 0.1 default for unit precision
    assert acc.char_cool.properties[PROP_MIN_STEP] == 0.1
    assert acc.char_heat.properties[PROP_MIN_STEP] == 0.1


async def test_heatercooler_fahrenheit(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test HeaterCooler with Fahrenheit units."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_MIN_TEMP: 45.0,  # Fahrenheit
        ATTR_MAX_TEMP: 95.0,  # Fahrenheit
        ATTR_TEMPERATURE: 68.0,  # Fahrenheit
        ATTR_CURRENT_TEMPERATURE: 65.0,
    }

    hass.config.units = US_CUSTOMARY_SYSTEM
    hass.states.async_set(entity_id, HVACMode.HEAT, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Target and current temperatures are converted from F to C for HomeKit
    assert acc.char_heat.value == 20.0  # 68F
    assert acc.char_cool.value == 20.0  # 68F
    assert acc.char_current_temp.value == pytest.approx(18.3, abs=0.1)  # 65F


async def test_heatercooler_fahrenheit_default_temp_range(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test the Celsius default range is not reconverted in Fahrenheit."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        # No min/max temp, so the Celsius defaults (7/35) are used as-is
        ATTR_TEMPERATURE: 68.0,
    }

    hass.config.units = US_CUSTOMARY_SYSTEM
    hass.states.async_set(entity_id, HVACMode.HEAT, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # The default bounds stay 7/35 C rather than being misread as Fahrenheit
    assert acc.char_cool.properties[PROP_MIN_VALUE] == 7.0
    assert acc.char_cool.properties[PROP_MAX_VALUE] == 35.0


async def test_heatercooler_state_updates(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test state updates from Home Assistant to HomeKit."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.OFF],
        ATTR_TEMPERATURE: 20.0,
        ATTR_CURRENT_TEMPERATURE: 18.0,
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Test heating mode
    hass.states.async_set(
        entity_id,
        HVACMode.HEAT,
        {
            **base_attrs,
            ATTR_HVAC_ACTION: HVACAction.HEATING,
            ATTR_TEMPERATURE: 22.0,
            ATTR_CURRENT_TEMPERATURE: 19.0,
        },
    )
    await hass.async_block_till_done()

    assert acc.char_active.value == 1
    assert acc.char_target_state.value == HC_TARGET_HEAT
    assert acc.char_current_state.value == HC_HEATING
    assert acc.char_heat.value == 22.0
    assert acc.char_cool.value == 22.0
    assert acc.char_current_temp.value == 19.0

    # Test cooling mode
    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {
            **base_attrs,
            ATTR_HVAC_ACTION: HVACAction.COOLING,
            ATTR_TEMPERATURE: 18.0,
            ATTR_CURRENT_TEMPERATURE: 21.0,
        },
    )
    await hass.async_block_till_done()

    assert acc.char_active.value == 1
    assert acc.char_target_state.value == HC_TARGET_COOL
    assert acc.char_current_state.value == HC_COOLING
    assert acc.char_heat.value == 18.0
    assert acc.char_cool.value == 18.0

    # Test auto mode
    hass.states.async_set(
        entity_id,
        HVACMode.AUTO,
        {
            **base_attrs,
            ATTR_HVAC_ACTION: HVACAction.IDLE,
            ATTR_TEMPERATURE: 20.0,
        },
    )
    await hass.async_block_till_done()

    assert acc.char_active.value == 1
    assert acc.char_target_state.value == HC_TARGET_AUTO
    assert acc.char_current_state.value == HC_IDLE


async def test_heatercooler_dual_temperature_support(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test HeaterCooler with dual temperature support (TARGET_TEMP_HIGH/LOW)."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.HEAT_COOL,
            HVACMode.OFF,
        ],
        ATTR_TARGET_TEMP_HIGH: 24.0,
        ATTR_TARGET_TEMP_LOW: 18.0,
        ATTR_CURRENT_TEMPERATURE: 21.0,
    }

    hass.states.async_set(entity_id, HVACMode.HEAT_COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    assert acc.char_cool.value == 24.0  # TARGET_TEMP_HIGH
    assert acc.char_heat.value == 18.0  # TARGET_TEMP_LOW

    # Update temperatures
    hass.states.async_set(
        entity_id,
        HVACMode.HEAT_COOL,
        {
            **base_attrs,
            ATTR_TARGET_TEMP_HIGH: 26.0,
            ATTR_TARGET_TEMP_LOW: 16.0,
        },
    )
    await hass.async_block_till_done()

    assert acc.char_cool.value == 26.0
    assert acc.char_heat.value == 16.0


async def test_heatercooler_fan_speed_updates(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test fan speed updates."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_FAN_MODES: [FAN_LOW, FAN_MIDDLE, FAN_MEDIUM, FAN_HIGH],
        ATTR_FAN_MODE: FAN_LOW,
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Test different fan speeds
    fan_speed_tests = [
        (FAN_LOW, 25),  # low -> 25% (index 0)
        (FAN_MIDDLE, 50),  # middle -> 50% (index 1)
        (FAN_MEDIUM, 75),  # medium -> 75% (index 2)
        (FAN_HIGH, 100),  # high -> 100% (index 3)
    ]

    for fan_mode, expected_percentage in fan_speed_tests:
        hass.states.async_set(
            entity_id, HVACMode.COOL, {**base_attrs, ATTR_FAN_MODE: fan_mode}
        )
        await hass.async_block_till_done()
        assert acc.char_speed.value == expected_percentage


async def test_heatercooler_swing_mode_updates(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test swing mode updates."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.SWING_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_SWING_MODES: ["off", "vertical", "horizontal", "both"],
        ATTR_SWING_MODE: "off",
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Test swing mode on/off
    swing_tests = [
        ("off", 0),
        ("vertical", 1),
        ("horizontal", 1),
        ("both", 1),
    ]

    for swing_mode, expected_value in swing_tests:
        hass.states.async_set(
            entity_id, HVACMode.COOL, {**base_attrs, ATTR_SWING_MODE: swing_mode}
        )
        await hass.async_block_till_done()
        assert acc.char_swing.value == expected_value


async def test_heatercooler_unavailable_states(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test handling of unavailable and unknown states."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Test unavailable state
    hass.states.async_set(entity_id, STATE_UNAVAILABLE, base_attrs)
    await hass.async_block_till_done()

    # Manually trigger state update since the test might not automatically trigger callbacks
    unavailable_state = hass.states.get(entity_id)
    acc.async_update_state(unavailable_state)

    assert acc.char_active.value == 0

    # Test unknown state
    hass.states.async_set(entity_id, STATE_UNKNOWN, base_attrs)
    await hass.async_block_till_done()

    unknown_state = hass.states.get(entity_id)
    acc.async_update_state(unknown_state)

    assert acc.char_active.value == 0


async def test_heatercooler_action_derivation(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test action derivation when hvac_action is not provided."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.HEAT_COOL,
            HVACMode.OFF,
        ],
        ATTR_TEMPERATURE: 20.0,
        ATTR_CURRENT_TEMPERATURE: 18.0,  # 2 degrees below target
    }

    hass.states.async_set(entity_id, HVACMode.HEAT, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Should derive heating action (current < target - delta)
    assert acc.char_current_state.value == HC_HEATING

    # Test cooling derivation
    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {
            **base_attrs,
            ATTR_CURRENT_TEMPERATURE: 22.0,  # 2 degrees above target
        },
    )
    await hass.async_block_till_done()

    assert acc.char_current_state.value == HC_COOLING

    # Test idle state (within delta)
    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {
            **base_attrs,
            ATTR_CURRENT_TEMPERATURE: 20.1,  # Within 0.25 delta
        },
    )
    await hass.async_block_till_done()

    assert acc.char_current_state.value == HC_IDLE


async def test_heatercooler_set_active_off(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test setting active to off via HomeKit."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.OFF],
    }

    hass.states.async_set(entity_id, HVACMode.HEAT, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    call_set_hvac_mode = async_mock_service(hass, CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE)
    call_set_temperature = async_mock_service(
        hass, CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE
    )

    # Turning off alongside a temperature write should only set the OFF mode
    acc._set_chars({CHAR_ACTIVE: 0, CHAR_COOLING_THRESHOLD_TEMPERATURE: 22.0})
    await hass.async_block_till_done()

    assert len(call_set_hvac_mode) == 1
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVACMode.OFF
    assert len(call_set_temperature) == 0


async def test_heatercooler_set_active_off_no_off_mode(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test turning off an entity without an OFF mode issues no service call."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.COOL],  # no OFF mode
        ATTR_FAN_MODES: ["low", "high"],
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    assert acc._supports_off is False

    call_set_hvac_mode = async_mock_service(hass, CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE)
    acc._set_chars({CHAR_ACTIVE: 0})
    await hass.async_block_till_done()

    assert len(call_set_hvac_mode) == 0


async def test_heatercooler_set_active_on(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test setting active to on via HomeKit."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.OFF],
    }

    # Start in OFF state
    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Set last known mode for test
    acc._last_known_mode = HVACMode.HEAT

    call_set_hvac_mode = async_mock_service(hass, CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE)

    # Set active to 1 (on) when currently off
    acc._set_chars({CHAR_ACTIVE: 1})
    await hass.async_block_till_done()

    assert len(call_set_hvac_mode) == 1
    assert call_set_hvac_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVACMode.HEAT


async def test_heatercooler_set_active_on_heat_only(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test turning a heat-only entity on uses a supported mode."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.OFF],
        ATTR_FAN_MODES: ["low", "high"],
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Off at startup must fall back to a supported mode, not COOL
    assert acc._last_known_mode == HVACMode.HEAT

    call_set_hvac_mode = async_mock_service(hass, CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE)
    acc._set_chars({CHAR_ACTIVE: 1})
    await hass.async_block_till_done()

    assert len(call_set_hvac_mode) == 1
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVACMode.HEAT


async def test_heatercooler_set_chars_dispatch_order(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test fan writes are dispatched after the mode and temperature writes."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_FAN_MODES: ["low", "high"],
        ATTR_FAN_MODE: "low",
        ATTR_TEMPERATURE: 20.0,
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    services: list[str] = []
    with patch.object(
        acc,
        "async_call_service",
        side_effect=lambda domain, service, data: services.append(service),
    ):
        acc._set_chars(
            {
                CHAR_ACTIVE: 1,
                CHAR_COOLING_THRESHOLD_TEMPERATURE: 22.0,
                CHAR_ROTATION_SPEED: 100,
            }
        )
        await hass.async_block_till_done()

    # Fan is dispatched after both the hvac mode and the temperature write
    assert services.index(SERVICE_SET_FAN_MODE) > services.index(SERVICE_SET_HVAC_MODE)
    assert services.index(SERVICE_SET_FAN_MODE) > services.index(
        SERVICE_SET_TEMPERATURE
    )


async def test_heatercooler_set_target_mode(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test setting target heater cooler state via HomeKit."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.OFF],
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    call_set_hvac_mode = async_mock_service(hass, CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE)

    # Test setting different target modes
    mode_tests = [
        (HC_TARGET_HEAT, HVACMode.HEAT),
        (HC_TARGET_COOL, HVACMode.COOL),
        (HC_TARGET_AUTO, HVACMode.AUTO),
    ]

    for hk_mode, _expected_ha_mode in mode_tests:
        acc._set_chars({CHAR_TARGET_HEATER_COOLER_STATE: hk_mode})
        await hass.async_block_till_done()

    assert len(call_set_hvac_mode) == 3
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVACMode.HEAT
    assert call_set_hvac_mode[1].data[ATTR_HVAC_MODE] == HVACMode.COOL
    assert call_set_hvac_mode[2].data[ATTR_HVAC_MODE] == HVACMode.AUTO


async def test_heatercooler_set_temperature_single(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test setting temperature for single-temperature entities."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_TEMPERATURE: 20.0,
    }

    hass.states.async_set(entity_id, HVACMode.HEAT, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    call_set_temperature = async_mock_service(
        hass, CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE
    )

    # Set heating temperature in HEAT mode
    acc._set_chars({CHAR_HEATING_THRESHOLD_TEMPERATURE: 22.0})
    await hass.async_block_till_done()

    assert len(call_set_temperature) == 1
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TEMPERATURE] == 22.0

    # Change to COOL mode and set cooling temperature
    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc._set_chars({CHAR_COOLING_THRESHOLD_TEMPERATURE: 18.0})
    await hass.async_block_till_done()

    assert len(call_set_temperature) == 2
    assert call_set_temperature[1].data[ATTR_TEMPERATURE] == 18.0


async def test_heatercooler_set_temperature_dual(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test setting temperature for dual-temperature entities."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.HEAT_COOL,
            HVACMode.OFF,
        ],
        ATTR_TARGET_TEMP_HIGH: 24.0,
        ATTR_TARGET_TEMP_LOW: 18.0,
    }

    hass.states.async_set(entity_id, HVACMode.HEAT_COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    call_set_temperature = async_mock_service(
        hass, CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE
    )

    # Set both temperatures
    acc._set_chars(
        {
            CHAR_COOLING_THRESHOLD_TEMPERATURE: 26.0,
            CHAR_HEATING_THRESHOLD_TEMPERATURE: 16.0,
        }
    )
    await hass.async_block_till_done()

    assert len(call_set_temperature) == 1
    assert call_set_temperature[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_HIGH] == 26.0
    assert call_set_temperature[0].data[ATTR_TARGET_TEMP_LOW] == 16.0


async def test_heatercooler_set_fan_speed(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test setting fan speed via HomeKit."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_FAN_MODES: [FAN_LOW, FAN_MIDDLE, FAN_MEDIUM, FAN_HIGH],
        ATTR_FAN_MODE: FAN_LOW,
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    call_set_fan_mode = async_mock_service(hass, CLIMATE_DOMAIN, SERVICE_SET_FAN_MODE)

    # Test different speed percentages
    speed_tests = [
        (0, None),  # 0% -> no service call
        (25, FAN_LOW),  # 25% -> low
        (50, FAN_MIDDLE),  # 50% -> middle
        (75, FAN_MEDIUM),  # 75% -> medium
        (100, FAN_HIGH),  # 100% -> high
    ]

    for speed_percent, _expected_fan_mode in speed_tests:
        acc._set_chars({CHAR_ROTATION_SPEED: speed_percent})
        await hass.async_block_till_done()

    # 0% is ignored, the remaining four map to each ordered speed
    assert len(call_set_fan_mode) == 4
    expected_calls = [FAN_LOW, FAN_MIDDLE, FAN_MEDIUM, FAN_HIGH]
    for i, expected_mode in enumerate(expected_calls):
        assert call_set_fan_mode[i].data[ATTR_FAN_MODE] == expected_mode


async def test_heatercooler_set_swing_mode(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test setting swing mode via HomeKit."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.SWING_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_SWING_MODES: ["off", "vertical", "horizontal", "both"],
        ATTR_SWING_MODE: "off",
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    call_set_swing_mode = async_mock_service(
        hass, CLIMATE_DOMAIN, SERVICE_SET_SWING_MODE
    )

    # Test swing on
    acc._set_chars({CHAR_SWING_MODE: 1})
    await hass.async_block_till_done()

    assert len(call_set_swing_mode) == 1
    assert call_set_swing_mode[0].data[ATTR_SWING_MODE] == "both"  # swing_on_mode

    # Test swing off
    acc._set_chars({CHAR_SWING_MODE: 0})
    await hass.async_block_till_done()

    assert len(call_set_swing_mode) == 2
    assert call_set_swing_mode[1].data[ATTR_SWING_MODE] == "off"  # SWING_OFF


async def test_heatercooler_capitalized_fan_modes(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test capitalized fan modes are sent back to the service unchanged."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_FAN_MODES: ["Auto", "Low", "Medium", "High"],
        ATTR_FAN_MODE: "Low",
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    call_set_fan_mode = async_mock_service(hass, CLIMATE_DOMAIN, SERVICE_SET_FAN_MODE)

    # The rotation speed writes must use the entity's original casing
    acc._set_chars({CHAR_ROTATION_SPEED: 100})
    await hass.async_block_till_done()
    assert call_set_fan_mode[-1].data[ATTR_FAN_MODE] == "High"

    acc._set_chars({CHAR_ROTATION_SPEED: 25})
    await hass.async_block_till_done()
    assert call_set_fan_mode[-1].data[ATTR_FAN_MODE] == "Low"


async def test_heatercooler_capitalized_swing_modes(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test capitalized swing modes are detected and preserved."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.SWING_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_SWING_MODES: ["Off", "On", "Both"],
        ATTR_SWING_MODE: "Off",
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Predefined swing modes are detected despite the capitalization
    assert acc.swing_on_mode == "On"
    assert acc.swing_off_mode == "Off"

    # On/off writes preserve the entity's original casing
    call_set_swing_mode = async_mock_service(
        hass, CLIMATE_DOMAIN, SERVICE_SET_SWING_MODE
    )
    acc._set_chars({CHAR_SWING_MODE: 1})
    await hass.async_block_till_done()
    assert call_set_swing_mode[0].data[ATTR_SWING_MODE] == "On"

    acc._set_chars({CHAR_SWING_MODE: 0})
    await hass.async_block_till_done()
    assert call_set_swing_mode[1].data[ATTR_SWING_MODE] == "Off"

    # A capitalized current swing value still reads as on
    hass.states.async_set(
        entity_id, HVACMode.COOL, {**base_attrs, ATTR_SWING_MODE: "On"}
    )
    await hass.async_block_till_done()
    assert acc.char_swing.value == 1


async def test_heatercooler_swing_mode_fallback(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test swing mode fallback when no swing modes are available."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.SWING_MODE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_SWING_MODES: [],  # Empty swing modes
        ATTR_SWING_MODE: None,
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    call_set_swing_mode = async_mock_service(
        hass, CLIMATE_DOMAIN, SERVICE_SET_SWING_MODE
    )

    # Test setting swing mode off when no swing modes are available
    # This should not make a service call because there are no swing modes
    acc._set_swing_mode(0)
    await hass.async_block_till_done()

    assert len(call_set_swing_mode) == 0


async def test_heatercooler_fan_speed_no_fan_modes(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test fan speed handling when no fan modes are available."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        # No fan modes
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    call_set_fan_mode = async_mock_service(hass, CLIMATE_DOMAIN, SERVICE_SET_FAN_MODE)

    # Test setting fan speed when no fan modes are available
    acc._set_fan_speed(50)
    await hass.async_block_till_done()

    # No service call should be made
    assert len(call_set_fan_mode) == 0


async def test_heatercooler_swing_mode_no_swing_attribute(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test swing mode handling when swing_on_mode attribute is not available."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        # No swing mode support
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    call_set_swing_mode = async_mock_service(
        hass, CLIMATE_DOMAIN, SERVICE_SET_SWING_MODE
    )

    # Test setting swing mode when swing_on_mode attribute is not available
    acc._set_swing_mode(1)
    await hass.async_block_till_done()

    # No service call should be made
    assert len(call_set_swing_mode) == 0


async def test_heatercooler_single_temp_no_entity_state(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test single temperature handling when entity state is not available."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_TEMPERATURE: 21.0,
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    call_set_temperature = async_mock_service(
        hass, CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE
    )

    # Remove entity state; a threshold write must not call the service
    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()

    acc._set_chars({CHAR_COOLING_THRESHOLD_TEMPERATURE: 22.0})
    await hass.async_block_till_done()

    assert len(call_set_temperature) == 0


@pytest.mark.parametrize(
    ("state", "current_temp", "chars", "expected"),
    [
        # Cool mode uses the cooling threshold; heat mode uses the heating one.
        pytest.param(
            HVACMode.COOL,
            20.0,
            {CHAR_COOLING_THRESHOLD_TEMPERATURE: 22.0},
            22.0,
            id="cool_uses_cooling_threshold",
        ),
        pytest.param(
            HVACMode.HEAT,
            20.0,
            {CHAR_HEATING_THRESHOLD_TEMPERATURE: 18.0},
            18.0,
            id="heat_uses_heating_threshold",
        ),
        # HEAT_COOL with both thresholds picks the one further from the temp.
        pytest.param(
            HVACMode.HEAT_COOL,
            19.0,
            {
                CHAR_COOLING_THRESHOLD_TEMPERATURE: 25.0,
                CHAR_HEATING_THRESHOLD_TEMPERATURE: 18.0,
            },
            25.0,  # |25-19| > |18-19|
            id="heat_cool_picks_further_cooling",
        ),
        pytest.param(
            HVACMode.HEAT_COOL,
            24.0,
            {
                CHAR_COOLING_THRESHOLD_TEMPERATURE: 25.0,
                CHAR_HEATING_THRESHOLD_TEMPERATURE: 18.0,
            },
            18.0,  # |18-24| > |25-24|
            id="heat_cool_picks_further_heating",
        ),
        # HEAT_COOL with a single threshold falls back to it.
        pytest.param(
            HVACMode.HEAT_COOL,
            20.0,
            {CHAR_COOLING_THRESHOLD_TEMPERATURE: 22.0},
            22.0,
            id="heat_cool_single_cooling",
        ),
        pytest.param(
            HVACMode.HEAT_COOL,
            20.0,
            {CHAR_HEATING_THRESHOLD_TEMPERATURE: 18.0},
            18.0,
            id="heat_cool_single_heating",
        ),
        # An unknown mode falls back to whichever threshold was written.
        pytest.param(
            "unknown_mode",
            20.0,
            {CHAR_COOLING_THRESHOLD_TEMPERATURE: 22.0},
            22.0,
            id="unknown_mode_cooling",
        ),
        pytest.param(
            "unknown_mode",
            20.0,
            {CHAR_HEATING_THRESHOLD_TEMPERATURE: 18.0},
            18.0,
            id="unknown_mode_heating",
        ),
    ],
)
async def test_heatercooler_complex_temperature_selection(
    hass: HomeAssistant,
    hk_driver: HomeDriver,
    state: str,
    current_temp: float,
    chars: dict[str, float],
    expected: float,
) -> None:
    """Test single set point selection driven by threshold characteristic writes."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.HEAT_COOL,
            HVACMode.OFF,
        ],
        ATTR_TEMPERATURE: current_temp,
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)
    acc.run()
    await hass.async_block_till_done()

    call_set_temperature = async_mock_service(
        hass, CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE
    )

    hass.states.async_set(entity_id, state, base_attrs)
    await hass.async_block_till_done()

    acc._set_chars(chars)
    await hass.async_block_till_done()

    assert call_set_temperature[-1].data[ATTR_TEMPERATURE] == pytest.approx(
        expected, abs=0.1
    )


@pytest.mark.parametrize(
    "state",
    [STATE_UNKNOWN, STATE_UNAVAILABLE, "invalid_mode", HVACMode.AUTO],
)
async def test_heatercooler_target_state_unchanged_for_unusable_states(
    hass: HomeAssistant, hk_driver: HomeDriver, state: str
) -> None:
    """Test the target state is left unchanged for states with no mapping."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)
    acc.run()
    await hass.async_block_till_done()

    # A known Cool target is established from the current state
    assert acc.char_target_state.value == HC_TARGET_COOL

    # Unknown, unavailable, invalid, and unsupported Auto have no mapping, so
    # the target characteristic keeps its previous value.
    hass.states.async_set(entity_id, state, base_attrs)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == HC_TARGET_COOL


async def test_heatercooler_derive_action_edge_case(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test the derived current state for modes without a heating/cooling action."""
    entity_id = "climate.test"
    features = ClimateEntityFeature.TARGET_TEMPERATURE
    hvac_modes = [
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.OFF,
    ]
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: features,
        ATTR_HVAC_MODES: hvac_modes,
        ATTR_TEMPERATURE: 21.0,
        ATTR_CURRENT_TEMPERATURE: 20.0,
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)
    acc.run()
    await hass.async_block_till_done()

    # Dry and fan modes have no heating/cooling action, so the state is idle
    hass.states.async_set(entity_id, HVACMode.DRY, base_attrs)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HC_IDLE

    hass.states.async_set(entity_id, HVACMode.FAN_ONLY, base_attrs)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HC_IDLE

    # Cool mode without a target temperature cannot derive an action
    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {
            ATTR_SUPPORTED_FEATURES: features,
            ATTR_HVAC_MODES: hvac_modes,
            ATTR_CURRENT_TEMPERATURE: 20.0,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HC_IDLE

    # Heat mode already at temperature is idle, not heating
    hass.states.async_set(
        entity_id,
        HVACMode.HEAT,
        {**base_attrs, ATTR_TEMPERATURE: 20.0, ATTR_CURRENT_TEMPERATURE: 21.0},
    )
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HC_IDLE


async def test_heatercooler_heat_cool_no_current_temp_diff(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test HEAT_COOL mode temperature selection when no current temperature available."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.HEAT_COOL,
            HVACMode.OFF,
        ],
        # No current temperature
    }

    # Create entity first
    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # HEAT_COOL with both thresholds but no current temp defaults to heating
    call_set_temperature = async_mock_service(
        hass, CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE
    )
    hass.states.async_set(entity_id, HVACMode.HEAT_COOL, base_attrs)
    await hass.async_block_till_done()

    acc._set_chars(
        {
            CHAR_COOLING_THRESHOLD_TEMPERATURE: 22.0,
            CHAR_HEATING_THRESHOLD_TEMPERATURE: 18.0,
        }
    )
    await hass.async_block_till_done()
    assert call_set_temperature[-1].data[ATTR_TEMPERATURE] == pytest.approx(
        18.0, abs=0.1
    )


async def test_heatercooler_derive_action_auto_without_thresholds(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test auto mode without thresholds derives to idle regardless of temp."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.AUTO, HVACMode.OFF],
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)
    acc.run()
    await hass.async_block_till_done()

    # Auto mode only inspects the high/low thresholds; with none present the
    # derived state is idle regardless of the current temperature.
    hass.states.async_set(
        entity_id, HVACMode.AUTO, {**base_attrs, ATTR_CURRENT_TEMPERATURE: 21.1}
    )
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HC_IDLE


async def test_heatercooler_fan_only_target_falls_back(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test a fan-only entity maps Auto to its mode and hides the thresholds."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.FAN_MODE,
        ATTR_HVAC_MODES: [HVACMode.FAN_ONLY, HVACMode.OFF],
        ATTR_FAN_MODES: ["low", "high"],
    }

    hass.states.async_set(entity_id, HVACMode.FAN_ONLY, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)
    acc.run()
    await hass.async_block_till_done()

    # No heat/cool/range mode, so Auto maps to the first supported mode
    valid_values = acc.char_target_state.properties["ValidValues"]
    assert valid_values == {HVACMode.FAN_ONLY: HC_TARGET_AUTO}
    assert acc.char_target_state.value == HC_TARGET_AUTO

    # No target temperature support, so the threshold sliders are not exposed
    assert not hasattr(acc, "char_cool")
    assert not hasattr(acc, "char_heat")
    assert acc.char_speed.value == 100


async def test_heatercooler_off_only_target_falls_back_to_off(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test a degenerate off-only entity maps Auto to off, not an unsupported mode."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.FAN_MODE,
        ATTR_HVAC_MODES: [HVACMode.OFF],
        ATTR_FAN_MODES: ["low", "high"],
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)
    acc.run()
    await hass.async_block_till_done()

    # The only mode is off, so Auto maps to off rather than an unsupported Auto
    valid_values = acc.char_target_state.properties["ValidValues"]
    assert valid_values == {HVACMode.OFF: HC_TARGET_AUTO}


async def test_heatercooler_derive_action_cooling_triggered(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test _derive_action returns COOLING for auto mode when temp is significantly higher than target."""
    entity_id = "climate.test"

    # Test entity in auto mode with current temp higher than target + delta
    # Target will be ATTR_TARGET_TEMP_HIGH (20.0), current temp should be > target + 0.25 (delta)
    hass.states.async_set(
        entity_id,
        HVACMode.AUTO,
        {
            ATTR_HVAC_MODES: [HVACMode.AUTO, HVACMode.OFF],
            ATTR_CURRENT_TEMPERATURE: 22.0,  # 2°C higher than target
            ATTR_TARGET_TEMP_HIGH: 20.0,  # Target (becomes the target in _derive_action)
            # Note: No ATTR_HVAC_ACTION so _derive_action gets called
        },
    )
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "HeaterCooler", entity_id, 1, None)
    hk_driver.add_accessory(acc)
    acc.run()
    await hass.async_block_till_done()

    # Current 22°C is above target 20°C plus the hysteresis band, so the
    # derived action is cooling.
    assert acc.char_current_state.value == HC_COOLING


async def test_heatercooler_zero_min_temp_preserved(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test a reported min temperature of 0 is used, not the default floor."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_MIN_TEMP: 0.0,
        ATTR_MAX_TEMP: 30.0,
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)
    acc.run()
    await hass.async_block_till_done()

    assert acc.char_cool.properties[PROP_MIN_VALUE] == 0.0


async def test_heatercooler_reports_humidity_via_linked_sensor(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test a reported current humidity is exposed via a linked sensor."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.COOL, HVACMode.OFF],
        ATTR_FAN_MODES: ["low", "high"],
        ATTR_CURRENT_HUMIDITY: 55,
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)
    acc.run()
    await hass.async_block_till_done()

    assert acc.char_current_humidity.value == 55

    hass.states.async_set(
        entity_id, HVACMode.COOL, {**base_attrs, ATTR_CURRENT_HUMIDITY: 60}
    )
    await hass.async_block_till_done()
    assert acc.char_current_humidity.value == 60


async def test_heatercooler_custom_fan_modes_no_rotation_speed(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test entities with only custom fan modes skip the rotation speed char."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        # Non-standard names that do not intersect the predefined speeds
        ATTR_FAN_MODES: ["quiet", "turbo"],
        ATTR_FAN_MODE: "quiet",
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    # This must not raise ZeroDivisionError during init
    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    assert acc.ordered_fan_speeds == []
    assert not hasattr(acc, "char_speed")


async def test_heatercooler_custom_swing_modes_no_swing_char(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test entities with only custom swing modes skip the swing char."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.SWING_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_SWING_MODES: ["off", "custom"],
        ATTR_SWING_MODE: "off",
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    assert acc.swing_on_mode is None
    assert not hasattr(acc, "char_swing")


async def test_heatercooler_derive_action_fahrenheit(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test derived action uses a unit independent hysteresis band."""
    entity_id = "climate.test"
    hass.config.units = US_CUSTOMARY_SYSTEM
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        # hvac_action intentionally omitted so the action is derived
        ATTR_TEMPERATURE: 68.0,
        ATTR_CURRENT_TEMPERATURE: 72.0,
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # 72F current vs 68F target in cool mode is well past the 0.25C band
    assert acc.char_current_state.value == HC_COOLING

    # Within the hysteresis band (0.2F ~= 0.11C < 0.25C) stays idle
    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {**base_attrs, ATTR_TEMPERATURE: 68.0, ATTR_CURRENT_TEMPERATURE: 68.2},
    )
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HC_IDLE


async def test_heatercooler_derive_action_auto_with_thresholds(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test derived action in auto mode using the target temperature range."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
        ATTR_HVAC_MODES: [HVACMode.HEAT_COOL, HVACMode.AUTO, HVACMode.OFF],
        # hvac_action intentionally omitted so the action is derived, and no
        # ATTR_TEMPERATURE so it falls back to the thresholds.
        ATTR_TARGET_TEMP_HIGH: 24.0,
        ATTR_TARGET_TEMP_LOW: 20.0,
        ATTR_CURRENT_TEMPERATURE: 26.0,
    }

    hass.states.async_set(entity_id, HVACMode.AUTO, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # 26°C is above the high threshold, so the derived action is cooling
    assert acc.char_current_state.value == HC_COOLING

    # Below the low threshold the derived action is heating
    hass.states.async_set(
        entity_id,
        HVACMode.AUTO,
        {**base_attrs, ATTR_CURRENT_TEMPERATURE: 18.0},
    )
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HC_HEATING

    # Comfortably between the thresholds it stays idle, not heating
    hass.states.async_set(
        entity_id,
        HVACMode.AUTO,
        {**base_attrs, ATTR_CURRENT_TEMPERATURE: 22.0},
    )
    await hass.async_block_till_done()
    assert acc.char_current_state.value == HC_IDLE
