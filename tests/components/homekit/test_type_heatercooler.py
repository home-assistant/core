"""Test different accessory types: HeaterCooler."""

from unittest.mock import patch

from homeassistant.components.climate import (
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
    DOMAIN as DOMAIN_CLIMATE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.homekit.const import (
    CHAR_ACTIVE,
    CHAR_COOLING_THRESHOLD_TEMPERATURE,
    CHAR_HEATING_THRESHOLD_TEMPERATURE,
    CHAR_ROTATION_SPEED,
    CHAR_SWING_MODE,
    CHAR_TARGET_HEATER_COOLER_STATE,
    CHAR_TARGET_TEMPERATURE,
    PROP_MAX_VALUE,
    PROP_MIN_STEP,
    PROP_MIN_VALUE,
)
from homeassistant.components.homekit.type_heatercooler import (
    HC_COOLING,
    HC_HEATING,
    HC_IDLE,
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
from homeassistant.core import Event, HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import async_mock_service


async def test_heatercooler_basic(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
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
    assert (
        acc.char_current_state.value == HC_IDLE
    )  # OFF mode without hvac_action derives to IDLE
    assert acc.char_target_state.value == HC_TARGET_AUTO
    assert acc.char_current_temp.value == 18.0
    assert acc.char_cool.value == 20.0
    assert acc.char_heat.value == 20.0

    # Check temperature properties
    assert acc.char_cool.properties[PROP_MIN_VALUE] == 10.0
    assert acc.char_cool.properties[PROP_MAX_VALUE] == 30.0
    assert acc.char_heat.properties[PROP_MIN_VALUE] == 10.0
    assert acc.char_heat.properties[PROP_MAX_VALUE] == 30.0


async def test_heatercooler_with_fan_and_swing(
    hass: HomeAssistant, hk_driver, events: list[Event]
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
        ATTR_FAN_MODES: [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH],
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
    assert acc.char_speed.value == 50  # FAN_LOW maps to 50% (index 1 out of 4 speeds)
    assert acc.char_swing.value == 0  # off


async def test_heatercooler_modes_auto_preferred(
    hass: HomeAssistant, hk_driver, events: list[Event]
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
    assert acc._supports_auto is True
    assert acc._hk_to_ha_target[HC_TARGET_AUTO] == HVACMode.AUTO


async def test_heatercooler_modes_heat_cool_fallback(
    hass: HomeAssistant, hk_driver, events: list[Event]
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
    assert acc._supports_auto is False
    assert acc._supports_heat_cool is True
    assert acc._hk_to_ha_target[HC_TARGET_AUTO] == HVACMode.HEAT_COOL


async def test_heatercooler_temperature_step(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test HeaterCooler temperature step configuration."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        "temperature_step": 0.5,
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    assert acc._step == 0.5
    assert acc.char_cool.properties[PROP_MIN_STEP] == 0.5
    assert acc.char_heat.properties[PROP_MIN_STEP] == 0.5


async def test_heatercooler_fahrenheit(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test HeaterCooler with Fahrenheit units."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_TEMPERATURE: 68.0,  # Fahrenheit
        ATTR_CURRENT_TEMPERATURE: 65.0,
        "temperature_step": 1.0,
    }

    hass.config.units = US_CUSTOMARY_SYSTEM
    hass.states.async_set(entity_id, HVACMode.HEAT, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Temperature step should be converted from F to C
    expected_step = 1.0 * 5.0 / 9.0  # F to C conversion
    assert abs(acc.char_cool.properties[PROP_MIN_STEP] - expected_step) < 0.01


async def test_heatercooler_state_updates(
    hass: HomeAssistant, hk_driver, events: list[Event]
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
    hass: HomeAssistant, hk_driver, events: list[Event]
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
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test fan speed updates."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_FAN_MODES: [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH],
        ATTR_FAN_MODE: FAN_AUTO,
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Test different fan speeds
    fan_speed_tests = [
        (FAN_AUTO, 25),  # auto -> 25% (index 0)
        (FAN_LOW, 50),  # low -> 50% (index 1)
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
    hass: HomeAssistant, hk_driver, events: list[Event]
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
    hass: HomeAssistant, hk_driver, events: list[Event]
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
    hass: HomeAssistant, hk_driver, events: list[Event]
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
    hass: HomeAssistant, hk_driver, events: list[Event]
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

    call_turn_off = async_mock_service(hass, DOMAIN_CLIMATE, SERVICE_TURN_OFF)

    # Set active to 0 (off)
    acc._set_chars({CHAR_ACTIVE: 0})
    await hass.async_block_till_done()

    assert len(call_turn_off) == 1
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id


async def test_heatercooler_set_active_on(
    hass: HomeAssistant, hk_driver, events: list[Event]
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

    call_set_hvac_mode = async_mock_service(hass, DOMAIN_CLIMATE, SERVICE_SET_HVAC_MODE)

    # Set active to 1 (on) when currently off
    acc._set_chars({CHAR_ACTIVE: 1})
    await hass.async_block_till_done()

    assert len(call_set_hvac_mode) == 1
    assert call_set_hvac_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_hvac_mode[0].data[ATTR_HVAC_MODE] == HVACMode.HEAT


async def test_heatercooler_set_target_mode(
    hass: HomeAssistant, hk_driver, events: list[Event]
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

    call_set_hvac_mode = async_mock_service(hass, DOMAIN_CLIMATE, SERVICE_SET_HVAC_MODE)

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
    hass: HomeAssistant, hk_driver, events: list[Event]
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
        hass, DOMAIN_CLIMATE, SERVICE_SET_TEMPERATURE
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
    hass: HomeAssistant, hk_driver, events: list[Event]
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
        hass, DOMAIN_CLIMATE, SERVICE_SET_TEMPERATURE
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
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test setting fan speed via HomeKit."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        ),
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_FAN_MODES: [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH],
        ATTR_FAN_MODE: FAN_AUTO,
    }

    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    call_set_fan_mode = async_mock_service(hass, DOMAIN_CLIMATE, SERVICE_SET_FAN_MODE)

    # Test different speed percentages
    speed_tests = [
        (0, FAN_AUTO),  # 0% -> auto (first in list)
        (25, FAN_LOW),  # 25% -> low
        (50, FAN_MEDIUM),  # 50% -> medium
        (75, FAN_HIGH),  # 75% -> high
        (100, FAN_HIGH),  # 100% -> high (last in list)
    ]

    for speed_percent, _expected_fan_mode in speed_tests:
        acc._set_chars({CHAR_ROTATION_SPEED: speed_percent})
        await hass.async_block_till_done()

    # Should have 4 calls, not 5, because 75% and 100% both map to FAN_HIGH
    # and our optimized code doesn't make redundant calls
    assert len(call_set_fan_mode) == 4
    expected_calls = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    for i, expected_mode in enumerate(expected_calls):
        assert call_set_fan_mode[i].data[ATTR_FAN_MODE] == expected_mode


async def test_heatercooler_set_swing_mode(
    hass: HomeAssistant, hk_driver, events: list[Event]
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
        hass, DOMAIN_CLIMATE, SERVICE_SET_SWING_MODE
    )

    # Test swing on
    acc._set_chars({CHAR_SWING_MODE: 1})
    await hass.async_block_till_done()

    assert len(call_set_swing_mode) == 1
    assert call_set_swing_mode[0].data[ATTR_SWING_MODE] == "vertical"  # swing_on_mode

    # Test swing off - since current mode is already "off", no service call should be made
    # This demonstrates our optimization to prevent redundant calls
    acc._set_chars({CHAR_SWING_MODE: 0})
    await hass.async_block_till_done()

    # Should still be 1 call because current state is already "off"
    assert len(call_set_swing_mode) == 1


async def test_heatercooler_service_errors(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test handling of service call errors."""
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

    with patch(
        "homeassistant.components.homekit.type_heatercooler.HeaterCooler.async_call_service",
        side_effect=ServiceValidationError("Service error"),
    ):
        # This should not raise an exception - errors should be logged
        acc._set_chars({CHAR_ACTIVE: 0})
        await hass.async_block_till_done()


async def test_heatercooler_service_call_exceptions(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test handling of service call exceptions in HeaterCooler."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.OFF],
        ATTR_FAN_MODES: ["low", "medium", "high"],
        ATTR_SWING_MODES: ["off", "vertical", "horizontal"],
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Mock service calls to raise exceptions
    with patch.object(
        acc, "async_call_service", side_effect=ServiceValidationError("Service error")
    ):
        # Test fan speed exception handling
        acc._set_fan_speed(50)
        await hass.async_block_till_done()

        # Test swing mode exception handling
        acc._set_swing_mode(1)
        await hass.async_block_till_done()

        # Test _set_chars exception handling
        acc._set_chars(
            {
                CHAR_ACTIVE: 1,
                CHAR_TARGET_HEATER_COOLER_STATE: HC_TARGET_HEAT,
                CHAR_TARGET_TEMPERATURE: 22.0,
                CHAR_ROTATION_SPEED: 75,
                CHAR_SWING_MODE: 1,
            }
        )
        await hass.async_block_till_done()


async def test_heatercooler_swing_mode_fallback(
    hass: HomeAssistant, hk_driver, events: list[Event]
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
        hass, DOMAIN_CLIMATE, SERVICE_SET_SWING_MODE
    )

    # Test setting swing mode off when no swing modes are available
    # This should not make a service call because there are no swing modes
    acc._set_swing_mode(0)
    await hass.async_block_till_done()

    assert len(call_set_swing_mode) == 0


async def test_heatercooler_swing_mode_no_entity_state(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test swing mode handling when entity state is not available."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.SWING_MODE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_SWING_MODES: ["off", "vertical"],
        ATTR_SWING_MODE: "off",
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    call_set_swing_mode = async_mock_service(
        hass, DOMAIN_CLIMATE, SERVICE_SET_SWING_MODE
    )

    # Remove entity state to trigger the return early
    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()

    # Test setting swing mode when entity state is not available
    acc._set_swing_mode(1)
    await hass.async_block_till_done()

    # No service call should be made
    assert len(call_set_swing_mode) == 0


async def test_heatercooler_fan_speed_no_fan_modes(
    hass: HomeAssistant, hk_driver, events: list[Event]
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

    call_set_fan_mode = async_mock_service(hass, DOMAIN_CLIMATE, SERVICE_SET_FAN_MODE)

    # Test setting fan speed when no fan modes are available
    acc._set_fan_speed(50)
    await hass.async_block_till_done()

    # No service call should be made
    assert len(call_set_fan_mode) == 0


async def test_heatercooler_swing_mode_no_swing_attribute(
    hass: HomeAssistant, hk_driver, events: list[Event]
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
        hass, DOMAIN_CLIMATE, SERVICE_SET_SWING_MODE
    )

    # Test setting swing mode when swing_on_mode attribute is not available
    acc._set_swing_mode(1)
    await hass.async_block_till_done()

    # No service call should be made
    assert len(call_set_swing_mode) == 0


async def test_heatercooler_temperature_step_exception(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test handling of invalid temperature step values."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_TEMPERATURE: 21.0,
        ATTR_MIN_TEMP: 7,
        ATTR_MAX_TEMP: 35,
        "temperature_step": "invalid",  # Invalid value that should trigger exception
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    acc.run()
    await hass.async_block_till_done()

    # Should have defaulted to 1.0 step due to exception
    assert acc._step == 1.0


async def test_heatercooler_temperature_conversion_methods(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test temperature conversion helper methods."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
        ATTR_TEMPERATURE: 21.0,
    }

    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    # Test Celsius
    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    acc.run()
    await hass.async_block_till_done()

    # Test temperature conversion methods
    homekit_temp = acc._temperature_to_homekit(21.0)
    assert homekit_temp == 21.0  # Should be same for Celsius

    ha_temp = acc._temperature_to_states(21.0)
    assert ha_temp == 21.0  # Should be same for Celsius

    # Test Fahrenheit
    hass.config.units = US_CUSTOMARY_SYSTEM
    acc_f = HeaterCooler(hass, hk_driver, "Climate", entity_id, 2, None)
    acc_f.run()
    await hass.async_block_till_done()

    # HomeKit always uses Celsius, so conversion should happen
    homekit_temp_f = acc_f._temperature_to_homekit(70.0)  # 70°F to Celsius
    assert abs(homekit_temp_f - 21.11) < 0.1  # Should be ~21.1°C

    ha_temp_f = acc_f._temperature_to_states(21.0)  # 21°C to Fahrenheit
    assert abs(ha_temp_f - 69.8) < 0.1  # Should be ~69.8°F


async def test_heatercooler_single_temp_no_entity_state(
    hass: HomeAssistant, hk_driver, events: list[Event]
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

    # Remove entity state to trigger the early return
    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()

    service_calls = []

    # This should trigger the early return when entity state is None
    acc._handle_single_temp_changes(service_calls, 22.0, None)

    # No service calls should be made when entity state is unavailable
    assert len(service_calls) == 0


async def test_heatercooler_complex_temperature_selection(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test complex temperature selection logic in single temperature mode."""
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
    }

    # Create entity first
    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Test COOL mode with cooling temperature
    hass.states.async_set(entity_id, HVACMode.COOL, base_attrs)
    await hass.async_block_till_done()

    service_calls = []
    acc._handle_single_temp_changes(service_calls, 22.0, None)
    assert len(service_calls) == 1
    assert service_calls[0][0] == "set_temperature"
    assert abs(service_calls[0][1][ATTR_TEMPERATURE] - 22.0) < 0.1

    # Test HEAT mode with heating temperature
    hass.states.async_set(entity_id, HVACMode.HEAT, base_attrs)
    await hass.async_block_till_done()

    service_calls = []
    acc._handle_single_temp_changes(service_calls, None, 18.0)
    assert len(service_calls) == 1
    assert service_calls[0][0] == "set_temperature"
    assert abs(service_calls[0][1][ATTR_TEMPERATURE] - 18.0) < 0.1

    # Test HEAT_COOL mode with both temperatures - cooling temp is more different from current
    hass.states.async_set(
        entity_id, HVACMode.HEAT_COOL, {**base_attrs, ATTR_TEMPERATURE: 19.0}
    )
    await hass.async_block_till_done()

    service_calls = []
    acc._handle_single_temp_changes(
        service_calls, 25.0, 18.0
    )  # cooling=25, heating=18, current=19
    assert len(service_calls) == 1
    assert service_calls[0][0] == "set_temperature"
    assert (
        abs(service_calls[0][1][ATTR_TEMPERATURE] - 25.0) < 0.1
    )  # Should pick cooling (more different: |25-19|=6 vs |18-19|=1)

    # Test HEAT_COOL mode with both temperatures - heating temp is more different from current
    hass.states.async_set(
        entity_id, HVACMode.HEAT_COOL, {**base_attrs, ATTR_TEMPERATURE: 24.0}
    )
    await hass.async_block_till_done()

    service_calls = []
    acc._handle_single_temp_changes(
        service_calls, 25.0, 18.0
    )  # cooling=25, heating=18, current=24
    assert len(service_calls) == 1
    assert service_calls[0][0] == "set_temperature"
    assert (
        abs(service_calls[0][1][ATTR_TEMPERATURE] - 18.0) < 0.1
    )  # Should pick heating (more different: |18-24|=6 vs |25-24|=1)

    # Test HEAT_COOL mode with only cooling temperature
    service_calls = []
    acc._handle_single_temp_changes(service_calls, 22.0, None)
    assert len(service_calls) == 1
    assert abs(service_calls[0][1][ATTR_TEMPERATURE] - 22.0) < 0.1

    # Test HEAT_COOL mode with only heating temperature
    service_calls = []
    acc._handle_single_temp_changes(service_calls, None, 18.0)
    assert len(service_calls) == 1
    assert abs(service_calls[0][1][ATTR_TEMPERATURE] - 18.0) < 0.1

    # Test unknown mode with cooling temperature (fallback behavior)
    hass.states.async_set(entity_id, "unknown_mode", base_attrs)
    await hass.async_block_till_done()

    service_calls = []
    acc._handle_single_temp_changes(service_calls, 22.0, None)
    assert len(service_calls) == 1
    assert abs(service_calls[0][1][ATTR_TEMPERATURE] - 22.0) < 0.1

    # Test unknown mode with heating temperature (fallback behavior)
    service_calls = []
    acc._handle_single_temp_changes(service_calls, None, 18.0)
    assert len(service_calls) == 1
    assert abs(service_calls[0][1][ATTR_TEMPERATURE] - 18.0) < 0.1


async def test_heatercooler_hk_target_mode_edge_cases(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test edge cases in _hk_target_mode method."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
    }

    # Create entity first
    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Test with STATE_UNKNOWN
    unknown_state = State(entity_id, STATE_UNKNOWN, base_attrs)
    result = acc._hk_target_mode(unknown_state)
    assert result is None

    # Test with STATE_UNAVAILABLE
    unavailable_state = State(entity_id, STATE_UNAVAILABLE, base_attrs)
    result = acc._hk_target_mode(unavailable_state)
    assert result is None

    # Test with invalid enum value
    invalid_state = State(entity_id, "invalid_mode", base_attrs)
    result = acc._hk_target_mode(invalid_state)
    assert result is None

    # Test with mode not supported by this entity instance
    # Create an entity that only supports heat/cool, then test auto mode
    limited_attrs = {
        **base_attrs,
        ATTR_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF],
    }
    hass.states.async_set(entity_id, HVACMode.OFF, limited_attrs)
    await hass.async_block_till_done()

    acc_limited = HeaterCooler(hass, hk_driver, "Climate", entity_id, 2, None)

    # Test auto mode when entity doesn't support auto/heat_cool
    auto_state = State(entity_id, HVACMode.AUTO, limited_attrs)
    # This should still work because AUTO maps to HC_TARGET_AUTO which is always in the mapping
    result = acc_limited._hk_target_mode(auto_state)
    assert result is not None


async def test_heatercooler_derive_action_edge_case(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test edge case in _derive_action that returns IDLE."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [
            HVACMode.DRY,
            HVACMode.OFF,
        ],  # Use DRY mode to trigger the final return
        ATTR_TEMPERATURE: 21.0,
        ATTR_CURRENT_TEMPERATURE: 20.0,
    }

    # Create entity first
    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Test DRY mode which should hit the final return HVACAction.IDLE
    dry_state = State(entity_id, HVACMode.DRY, base_attrs)
    result = acc._derive_action(dry_state)
    assert result == HVACAction.IDLE

    # Test FAN mode which should also hit the final return
    fan_state = State(entity_id, HVACMode.FAN_ONLY, base_attrs)
    result = acc._derive_action(fan_state)
    assert result == HVACAction.IDLE


async def test_heatercooler_heat_cool_no_current_temp_diff(
    hass: HomeAssistant, hk_driver, events: list[Event]
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

    # Test HEAT_COOL mode with both temperatures but no current temperature
    hass.states.async_set(entity_id, HVACMode.HEAT_COOL, base_attrs)
    await hass.async_block_till_done()

    service_calls = []
    acc._handle_single_temp_changes(service_calls, 22.0, 18.0)
    assert len(service_calls) == 1
    assert service_calls[0][0] == "set_temperature"
    # Should default to heating temperature when no current temp available
    assert abs(service_calls[0][1][ATTR_TEMPERATURE] - 18.0) < 0.1


async def test_heatercooler_hk_target_mode_unsupported(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test _hk_target_mode returns None for unsupported modes."""
    entity_id = "climate.test"
    base_attrs = {
        ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.TARGET_TEMPERATURE,
        ATTR_HVAC_MODES: [
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.OFF,
        ],  # No AUTO or HEAT_COOL
    }

    # Create entity first
    hass.states.async_set(entity_id, HVACMode.OFF, base_attrs)
    await hass.async_block_till_done()

    # Create accessory that doesn't support auto/heat_cool
    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Manually remove AUTO from the mapping to force the None return
    original_mapping = acc._hk_to_ha_target.copy()
    if HC_TARGET_AUTO in acc._hk_to_ha_target:
        del acc._hk_to_ha_target[HC_TARGET_AUTO]

    # Test with auto mode - should return None when not in mapping
    auto_state = State(entity_id, HVACMode.AUTO, base_attrs)
    result = acc._hk_target_mode(auto_state)
    assert result is None

    # Restore the mapping
    acc._hk_to_ha_target = original_mapping


async def test_heatercooler_derive_action_final_idle(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test _derive_action returns IDLE via the final return statement."""
    entity_id = "climate.test"

    # Create entity first
    hass.states.async_set(entity_id, HVACMode.OFF, {})
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "Climate", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Test case 1: Mode that's not COOL, HEAT, AUTO, or HEAT_COOL
    # This should skip all the if conditions and hit the final return
    base_attrs = {
        ATTR_TEMPERATURE: 21.0,
        ATTR_CURRENT_TEMPERATURE: 20.0,
    }

    # DRY mode should reach the final return HVACAction.IDLE
    dry_state = State(entity_id, HVACMode.DRY, base_attrs)
    result = acc._derive_action(dry_state)
    assert result == HVACAction.IDLE

    # Test case 2: AUTO mode within hysteresis (should also hit final return)
    # Current temp within hysteresis range (21.0 ± 0.25)
    auto_attrs = {
        ATTR_TEMPERATURE: 21.0,
        ATTR_CURRENT_TEMPERATURE: 21.1,  # Within hysteresis range
    }
    auto_state = State(entity_id, HVACMode.AUTO, auto_attrs)
    result = acc._derive_action(auto_state)
    assert result == HVACAction.IDLE


async def test_heatercooler_derive_action_cooling_triggered(
    hass: HomeAssistant, hk_driver
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

    acc = HeaterCooler(hass, hk_driver, "HeaterCooler", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    # With temp 22°C and target 20°C, current > target + delta (20.25)
    # This should trigger: return HVACAction.COOLING in _derive_action (line 571)
    assert acc.char_current_state.value == HC_COOLING


async def test_heatercooler_get_temperature_range(
    hass: HomeAssistant, hk_driver
) -> None:
    """Test temperature range calculation."""
    entity_id = "climate.test"

    # Test with default range
    hass.states.async_set(entity_id, HVACMode.OFF, {})
    await hass.async_block_till_done()

    acc = HeaterCooler(hass, hk_driver, "HeaterCooler", entity_id, 2, None)
    state = hass.states.get(entity_id)
    assert state
    assert acc.get_temperature_range(state) == (7.0, 35.0)

    # Test with custom range
    hass.states.async_set(
        entity_id,
        HVACMode.COOL,
        {ATTR_MIN_TEMP: 20, ATTR_MAX_TEMP: 25},
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert acc.get_temperature_range(state) == (20, 25)
