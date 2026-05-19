"""Tests for the IntesisHome climate platform."""

import pytest

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_BOOST,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_DEVICE_ID,
    MOCK_VAL_OUT_TEMP,
    MOCK_VAL_SETPOINT,
    MOCK_VAL_TEMP,
    PLATFORM_CONFIG,
)

ENTITY_ID = "climate.mock_device"


async def setup_platform(hass: HomeAssistant, mock_controller) -> None:
    """Set up the intesishome platform with the mock controller."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, PLATFORM_CONFIG)
    await hass.async_block_till_done()


async def test_setup_creates_entity(hass: HomeAssistant, mock_controller) -> None:
    """Entity is created for each device returned by the controller."""
    await setup_platform(hass, mock_controller)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.name == "MOCK DEVICE"


async def test_unique_id(hass: HomeAssistant, mock_controller) -> None:
    """Unique ID matches the device ID from the controller."""
    await setup_platform(hass, mock_controller)
    registry = er.async_get(hass)
    entry = registry.async_get(ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == MOCK_DEVICE_ID


# --- Feature flags ---


async def test_supported_features_full(hass: HomeAssistant, mock_controller) -> None:
    """All features enabled when controller reports full capabilities."""
    await setup_platform(hass, mock_controller)
    state = hass.states.get(ENTITY_ID)
    features = state.attributes["supported_features"]
    assert features & ClimateEntityFeature.TARGET_TEMPERATURE
    assert features & ClimateEntityFeature.SWING_MODE
    assert features & ClimateEntityFeature.FAN_MODE
    assert features & ClimateEntityFeature.PRESET_MODE
    assert features & ClimateEntityFeature.TURN_ON
    assert features & ClimateEntityFeature.TURN_OFF


async def test_supported_features_minimal(hass: HomeAssistant, mock_controller) -> None:
    """Only TURN_ON/TURN_OFF when controller reports no optional capabilities."""
    mock_controller.has_setpoint_control.return_value = False
    mock_controller.has_vertical_swing.return_value = False
    mock_controller.has_horizontal_swing.return_value = False
    mock_controller.get_fan_speed_list.return_value = []
    mock_controller.get_devices.return_value = {
        MOCK_DEVICE_ID: {"name": "MOCK DEVICE"}  # no climate_working_mode
    }
    await setup_platform(hass, mock_controller)
    state = hass.states.get(ENTITY_ID)
    features = state.attributes["supported_features"]
    assert features & ClimateEntityFeature.TURN_ON
    assert features & ClimateEntityFeature.TURN_OFF
    assert not (features & ClimateEntityFeature.TARGET_TEMPERATURE)
    assert not (features & ClimateEntityFeature.SWING_MODE)
    assert not (features & ClimateEntityFeature.FAN_MODE)
    assert not (features & ClimateEntityFeature.PRESET_MODE)


# --- HVAC mode mapping ---


@pytest.mark.parametrize(
    ("ih_mode", "expected_hvac_mode"),
    [
        ("auto", HVACMode.HEAT_COOL),
        ("cool", HVACMode.COOL),
        ("dry", HVACMode.DRY),
        ("fan", HVACMode.FAN_ONLY),
        ("heat", HVACMode.HEAT),
    ],
)
async def test_hvac_mode_mapping(
    hass: HomeAssistant, mock_controller, ih_mode, expected_hvac_mode
) -> None:
    """IH mode strings map to the correct HA HVACMode."""
    mock_controller.get_mode.return_value = ih_mode
    mock_controller.is_on.return_value = True
    await setup_platform(hass, mock_controller)
    state = hass.states.get(ENTITY_ID)
    assert state.state == expected_hvac_mode


async def test_hvac_mode_off_when_power_off(
    hass: HomeAssistant, mock_controller
) -> None:
    """State is OFF when device power is off, regardless of reported mode."""
    mock_controller.is_on.return_value = False
    mock_controller.get_mode.return_value = "cool"
    await setup_platform(hass, mock_controller)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def test_unknown_hvac_mode_skipped(
    hass: HomeAssistant, mock_controller, caplog: pytest.LogCaptureFixture
) -> None:
    """Unknown mode strings from get_mode_list log a warning and are skipped."""
    mock_controller.get_mode_list.return_value = ["cool", "heat+tank", "heat"]
    await setup_platform(hass, mock_controller)
    assert "heat+tank" in caplog.text
    state = hass.states.get(ENTITY_ID)
    hvac_modes = state.attributes["hvac_modes"]
    assert HVACMode.COOL in hvac_modes
    assert HVACMode.HEAT in hvac_modes
    assert HVACMode.OFF in hvac_modes
    # The unknown mode must not appear as a valid HA mode
    assert "heat+tank" not in hvac_modes


# --- State attributes ---


async def test_current_temperature(hass: HomeAssistant, mock_controller) -> None:
    """Current temperature is read from the controller."""
    await setup_platform(hass, mock_controller)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes["current_temperature"] == MOCK_VAL_TEMP


async def test_target_temperature(hass: HomeAssistant, mock_controller) -> None:
    """Target temperature is read from the controller when on."""
    await setup_platform(hass, mock_controller)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes["temperature"] == MOCK_VAL_SETPOINT


async def test_outdoor_temp_in_attributes(hass: HomeAssistant, mock_controller) -> None:
    """Outdoor temperature appears in extra state attributes when present."""
    await setup_platform(hass, mock_controller)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes["outdoor_temp"] == MOCK_VAL_OUT_TEMP


async def test_outdoor_temp_absent_when_none(
    hass: HomeAssistant, mock_controller
) -> None:
    """Outdoor temperature attribute is omitted when controller returns None."""
    mock_controller.get_outdoor_temperature.return_value = None
    await setup_platform(hass, mock_controller)
    state = hass.states.get(ENTITY_ID)
    assert "outdoor_temp" not in state.attributes


async def test_power_consumption_in_attributes(
    hass: HomeAssistant, mock_controller
) -> None:
    """Power consumption appears in attributes (converted W→kW) when non-None."""
    mock_controller.get_heat_power_consumption.return_value = 1500
    mock_controller.get_cool_power_consumption.return_value = 2000
    await setup_platform(hass, mock_controller)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes["power_consumption_heat_kw"] == 1.5
    assert state.attributes["power_consumption_cool_kw"] == 2.0


# --- Climate operations ---


async def test_set_hvac_mode_off(hass: HomeAssistant, mock_controller) -> None:
    """Setting OFF calls set_power_off and updates local state."""
    await setup_platform(hass, mock_controller)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    mock_controller.set_power_off.assert_called_once_with(MOCK_DEVICE_ID)
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def test_set_hvac_mode_powers_on_if_off(
    hass: HomeAssistant, mock_controller
) -> None:
    """Setting a non-OFF mode powers on the device first if it is off."""
    mock_controller.is_on.return_value = False
    await setup_platform(hass, mock_controller)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    mock_controller.set_power_on.assert_called_once_with(MOCK_DEVICE_ID)
    mock_controller.set_mode.assert_called_once_with(MOCK_DEVICE_ID, "cool")


async def test_set_temperature(hass: HomeAssistant, mock_controller) -> None:
    """set_temperature calls the controller with the correct value."""
    await setup_platform(hass, mock_controller)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.0},
        blocking=True,
    )
    mock_controller.set_temperature.assert_called_once_with(MOCK_DEVICE_ID, 22.0)


async def test_set_fan_mode(hass: HomeAssistant, mock_controller) -> None:
    """set_fan_mode calls set_fan_speed on the controller."""
    await setup_platform(hass, mock_controller)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, "fan_mode": "high"},
        blocking=True,
    )
    mock_controller.set_fan_speed.assert_called_once_with(MOCK_DEVICE_ID, "high")


async def test_set_preset_mode(hass: HomeAssistant, mock_controller) -> None:
    """set_preset_mode translates to the IH preset name."""
    await setup_platform(hass, mock_controller)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_BOOST},
        blocking=True,
    )
    mock_controller.set_preset_mode.assert_called_once_with(MOCK_DEVICE_ID, "powerful")


@pytest.mark.parametrize(
    ("ha_swing", "expected_vvane", "expected_hvane"),
    [
        (SWING_OFF, "auto/stop", "auto/stop"),
        (SWING_BOTH, "swing", "swing"),
        (SWING_VERTICAL, "swing", "auto/stop"),
        (SWING_HORIZONTAL, "auto/stop", "swing"),
    ],
)
async def test_set_swing_mode(
    hass: HomeAssistant,
    mock_controller,
    ha_swing,
    expected_vvane,
    expected_hvane,
) -> None:
    """set_swing_mode maps composite HA swing modes to vvane/hvane correctly."""
    await setup_platform(hass, mock_controller)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: ha_swing},
        blocking=True,
    )
    mock_controller.set_vertical_vane.assert_called_once_with(
        MOCK_DEVICE_ID, expected_vvane
    )
    mock_controller.set_horizontal_vane.assert_called_once_with(
        MOCK_DEVICE_ID, expected_hvane
    )


async def test_turn_on(hass: HomeAssistant, mock_controller) -> None:
    """turn_on calls set_power_on."""
    mock_controller.is_on.return_value = False
    await setup_platform(hass, mock_controller)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_controller.set_power_on.assert_called_with(MOCK_DEVICE_ID)


async def test_turn_off(hass: HomeAssistant, mock_controller) -> None:
    """turn_off calls set_power_off."""
    await setup_platform(hass, mock_controller)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_controller.set_power_off.assert_called_with(MOCK_DEVICE_ID)


# --- Availability ---


async def test_available_when_connected(hass: HomeAssistant, mock_controller) -> None:
    """Entity is available when the controller is connected."""
    mock_controller.is_connected = True
    await setup_platform(hass, mock_controller)
    state = hass.states.get(ENTITY_ID)
    assert state.state != "unavailable"


async def test_unavailable_after_disconnect(
    hass: HomeAssistant, mock_controller
) -> None:
    """Entity becomes unavailable after a connection drop is reported via callback."""
    await setup_platform(hass, mock_controller)

    # Simulate a connection drop by firing the registered update callback
    mock_controller.is_connected = False
    callback = mock_controller.add_update_callback.call_args[0][0]
    await callback()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == "unavailable"


# --- swing_mode property ---


@pytest.mark.parametrize(
    ("vvane", "hvane", "expected_swing"),
    [
        ("swing", "swing", SWING_BOTH),
        ("swing", "auto/stop", SWING_VERTICAL),
        ("auto/stop", "swing", SWING_HORIZONTAL),
        ("auto/stop", "auto/stop", SWING_OFF),
    ],
)
async def test_swing_mode_property(
    hass: HomeAssistant, mock_controller, vvane, hvane, expected_swing
) -> None:
    """swing_mode property maps vvane/hvane values to composite HA swing modes."""
    mock_controller.get_vertical_swing.return_value = vvane
    mock_controller.get_horizontal_swing.return_value = hvane
    await setup_platform(hass, mock_controller)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes["swing_mode"] == expected_swing
