"""Tests for the BSB-LAN climate platform."""

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

from bsblan import BSBLANError, HeatingCircuitStatus, State, StaticState
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bsblan.const import DOMAIN
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_COMFORT,
    PRESET_ECO,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant, State as HassState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.state import async_reproduce_state

from . import setup_with_selected_platforms

ENTITY_ID = "climate.heating_circuit_1"


def _temp_param(value: str) -> dict[str, Any]:
    """Build a raw BSB-LAN temperature parameter payload."""
    return {
        "name": "",
        "value": value,
        "unit": "&deg;C",
        "desc": "",
        "dataType": 0,
        "readonly": 0,
        "error": 0,
    }


def _circuit_state(hvac_mode: int, current_setpoint: str | None) -> State:
    """Build a circuit state with a comfort setpoint of 20.0."""
    data: dict[str, Any] = {
        "hvac_mode": {**_temp_param(str(hvac_mode)), "dataType": 1, "unit": ""},
        "target_temperature": _temp_param("20.0"),
    }
    if current_setpoint is not None:
        data["current_setpoint"] = _temp_param(current_setpoint)
    return State.model_validate(data)


@pytest.mark.parametrize(
    ("static_data", "expected_min", "expected_max"),
    [
        pytest.param(
            {
                "heating_protective_setpoint": _temp_param("10.0"),
                "comfort_setpoint_max": _temp_param("26.0"),
            },
            10.0,
            26.0,
            id="standard_device",
        ),
        pytest.param(
            {
                "min_temp": _temp_param("8.0"),
                "max_temp": _temp_param("20.0"),
            },
            8.0,
            20.0,
            id="pps_device",
        ),
        pytest.param(
            {
                "heating_protective_setpoint": _temp_param("---"),
                "comfort_setpoint_max": _temp_param("---"),
                "min_temp": _temp_param("8.0"),
                "max_temp": _temp_param("20.0"),
            },
            8.0,
            20.0,
            id="inactive_preferred_source",
        ),
        pytest.param(
            {
                "heating_protective_setpoint": _temp_param("---"),
                "comfort_setpoint_max": _temp_param("---"),
            },
            DEFAULT_MIN_TEMP,
            DEFAULT_MAX_TEMP,
            id="all_sources_inactive",
        ),
    ],
)
async def test_climate_min_max_temperature(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    static_data: dict[str, Any],
    expected_min: float,
    expected_max: float,
) -> None:
    """Test min/max temperature bounds resolved from per-circuit static values."""
    mock_bsblan.static_values.return_value = StaticState.model_validate(static_data)

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["min_temp"] == expected_min
    assert state.attributes["max_temp"] == expected_max


async def test_celsius_fahrenheit(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Celsius and Fahrenheit temperature units."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_climate_entity_loads_without_static_values(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the climate entity still loads when static values are unavailable."""
    mock_bsblan.static_values.side_effect = BSBLANError("General error")

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["current_temperature"] is not None


async def test_climate_without_presets_on_pps(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test PPS devices do not offer presets."""
    device = mock_bsblan.device.return_value
    mock_bsblan.device.return_value = device.model_copy(update={"bus": "PPS"})

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert "preset_modes" not in state.attributes
    assert not state.attributes["supported_features"] & ClimateEntityFeature.PRESET_MODE


async def test_climate_entity_properties(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the climate entity properties."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Test target_temperature
    mock_target_temp = MagicMock()
    mock_target_temp.value = 23.5
    mock_bsblan.state.return_value.target_temperature = mock_target_temp

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["temperature"] == 23.5

    # Test hvac_mode - BSB-LAN returns integer: 1=auto
    mock_hvac_mode = MagicMock()
    mock_hvac_mode.value = 1  # auto mode
    mock_bsblan.state.return_value.hvac_mode = mock_hvac_mode

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.AUTO

    # Test preset_mode - BSB-LAN mode 2 is eco/reduced
    mock_hvac_mode.value = 2  # eco mode

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.HEAT
    assert state.attributes["preset_mode"] == PRESET_ECO

    # Test hvac_action mapping
    mock_hvac_action = MagicMock()
    mock_hvac_action.value = HeatingCircuitStatus.COOLING_ACTIVE
    mock_bsblan.state.return_value.hvac_action = mock_hvac_action

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["hvac_action"] == HVACAction.COOLING


async def _async_set_hvac_action(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    freezer: FrozenDateTimeFactory,
    value: MagicMock | None,
) -> HVACAction | None:
    """Helper to push a new hvac_action value through coordinator."""
    mock_bsblan.state.return_value.hvac_action = value
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    return state.attributes.get("hvac_action")


async def test_hvac_action_handles_none_inputs(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure hvac_action gracefully handles None values."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    assert await _async_set_hvac_action(hass, mock_bsblan, freezer, None) is None

    mock_action = MagicMock()
    mock_action.value = None
    assert await _async_set_hvac_action(hass, mock_bsblan, freezer, mock_action) is None


async def test_hvac_action_uses_library_mapping(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify hvac_action correctly uses library's status code mapping."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Test a known status code is converted to action
    mock_action = MagicMock()
    mock_action.value = HeatingCircuitStatus.HEATING_COMFORT
    result = await _async_set_hvac_action(hass, mock_bsblan, freezer, mock_action)
    assert result == HVACAction.HEATING

    # Test unknown status code defaults to IDLE
    mock_action.value = 1  # Unknown status code
    result = await _async_set_hvac_action(hass, mock_bsblan, freezer, mock_action)
    assert result == HVACAction.IDLE


async def test_climate_without_current_temperature_sensor(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test climate entity when current temperature sensor is not available."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Set current_temperature to None to simulate no temperature sensor
    mock_bsblan.state.return_value.current_temperature = None

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should not crash and current_temperature should be None in attributes
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["current_temperature"] is None


async def test_climate_without_target_temperature_sensor(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test climate entity when target temperature sensor is not available."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Set target_temperature to None to simulate no temperature sensor
    mock_bsblan.state.return_value.target_temperature = None

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should not crash and target temperature should be None in attributes
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["temperature"] is None


async def test_climate_hvac_mode_object_none(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test climate entity when hvac_mode object itself is None."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Set hvac_mode to None (the object itself, not just the value)
    mock_bsblan.state.return_value.hvac_mode = None

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # State should be unknown when hvac_mode object is None
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["preset_mode"] is None


# Mapping from HA HVACMode to BSB-Lan integer values for test assertions
HA_TO_BSBLAN_HVAC_MODE_TEST: dict[HVACMode, int] = {
    HVACMode.OFF: 0,
    HVACMode.AUTO: 1,
    HVACMode.HEAT: 3,
}


@pytest.mark.parametrize(
    ("hvac_mode_int", "mode"),
    [(1, HVACMode.HEAT), (3, HVACMode.AUTO), (3, HVACMode.OFF)],
)
async def test_async_set_hvac_mode(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hvac_mode_int: int,
    mode: HVACMode,
) -> None:
    """Test setting HVAC mode via service call."""
    mock_bsblan.state.return_value = _circuit_state(hvac_mode_int, None)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Call the service to set HVAC mode
    await hass.services.async_call(
        domain=CLIMATE_DOMAIN,
        service=SERVICE_SET_HVAC_MODE,
        service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: mode},
        blocking=True,
    )

    # Assert that the thermostat method was called with integer value
    expected_int = HA_TO_BSBLAN_HVAC_MODE_TEST[mode]
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=expected_int, circuit=1)
    mock_bsblan.thermostat.reset_mock()


@pytest.mark.parametrize(
    ("hvac_mode_int", "mode"),
    [(3, HVACMode.HEAT), (2, HVACMode.HEAT), (1, HVACMode.AUTO), (0, HVACMode.OFF)],
)
async def test_set_hvac_mode_already_active(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hvac_mode_int: int,
    mode: HVACMode,
) -> None:
    """Test setting the HVAC mode the circuit is already in writes nothing."""
    mock_bsblan.state.return_value = _circuit_state(hvac_mode_int, None)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: mode},
        blocking=True,
    )

    mock_bsblan.thermostat.assert_not_called()


@pytest.mark.parametrize(
    ("hvac_mode_int", "preset_mode", "expected_call"),
    [
        # Automatic mode: temporary override until the next switch point
        (1, PRESET_COMFORT, {"temporary_mode": 2}),
        (1, PRESET_ECO, {"temporary_mode": 1}),
        # Other modes: switch the permanent operating mode
        (3, PRESET_ECO, {"hvac_mode": 2}),
        (2, PRESET_COMFORT, {"hvac_mode": 3}),
        (0, PRESET_ECO, {"hvac_mode": 2}),
    ],
)
async def test_async_set_preset_mode_success(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hvac_mode_int: int,
    preset_mode: str,
    expected_call: dict[str, int],
) -> None:
    """Test setting preset mode via service call."""
    mock_bsblan.state.return_value = _circuit_state(hvac_mode_int, None)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset_mode},
        blocking=True,
    )

    mock_bsblan.thermostat.assert_called_once_with(**expected_call, circuit=1)


@pytest.mark.parametrize(
    ("target_temp"),
    [
        (8.0),  # Min temperature
        (15.0),  # Mid-range temperature
        (20.0),  # Max temperature
    ],
)
async def test_async_set_temperature(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    target_temp: float,
) -> None:
    """Test setting temperature via service call."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await hass.services.async_call(
        domain=CLIMATE_DOMAIN,
        service=SERVICE_SET_TEMPERATURE,
        service_data={ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: target_temp},
        blocking=True,
    )
    # Assert that the thermostat method was called with the correct temperature
    mock_bsblan.thermostat.assert_called_once_with(
        target_temperature=target_temp, circuit=1
    )


async def test_async_set_data(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting data via service calls."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    # Test setting temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 19},
        blocking=True,
    )
    mock_bsblan.thermostat.assert_called_once_with(target_temperature=19, circuit=1)
    mock_bsblan.thermostat.reset_mock()

    # Test setting HVAC mode - should convert to integer (1=auto)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.AUTO},
        blocking=True,
    )
    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=1, circuit=1)  # 1 = auto
    mock_bsblan.thermostat.reset_mock()

    # Test setting preset mode to ECO in heat mode - should use integer 2
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_ECO},
        blocking=True,
    )
    mock_bsblan.thermostat.assert_called_once_with(
        hvac_mode=2, circuit=1
    )  # 2 = eco/reduced
    mock_bsblan.thermostat.reset_mock()

    # Test error handling
    mock_bsblan.thermostat.side_effect = BSBLANError("Test error")
    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 20},
            blocking=True,
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "set_data_error"


async def test_dual_circuit_climate_entities(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry_dual_circuit: MockConfigEntry,
) -> None:
    """Test that dual-circuit config creates two climate entities with correct IDs."""
    await setup_with_selected_platforms(
        hass, mock_config_entry_dual_circuit, [Platform.CLIMATE]
    )

    # Circuit 1 entity should exist
    state1 = hass.states.get("climate.heating_circuit_1")
    assert state1 is not None

    # Circuit 2 entity should exist
    state2 = hass.states.get("climate.heating_circuit_2")
    assert state2 is not None


@pytest.mark.parametrize(
    ("hvac_mode_int", "status", "expected_action"),
    [
        (1, HeatingCircuitStatus.OFF, HVACAction.IDLE),
        (0, HeatingCircuitStatus.OFF, HVACAction.OFF),
        (0, HeatingCircuitStatus.FROST_PROTECTION, HVACAction.HEATING),
    ],
)
async def test_hvac_action_in_protection_mode(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hvac_mode_int: int,
    status: int,
    expected_action: HVACAction,
) -> None:
    """Test an idle circuit reports off in protection mode, unless it heats."""
    mock_bsblan.state.return_value.hvac_mode = MagicMock(value=hvac_mode_int)
    mock_bsblan.state.return_value.hvac_action = MagicMock(value=status)

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    assert hass.states.get(ENTITY_ID).attributes["hvac_action"] == expected_action


@pytest.fixture
def mock_reduced_setpoint(mock_bsblan: AsyncMock) -> None:
    """Mock a reduced setpoint of 17.0 in the circuit config."""
    mock_bsblan.static_values.return_value = StaticState.model_validate(
        {
            "temp_reduced_setpoint": _temp_param("17.0"),
            "heating_protective_setpoint": _temp_param("8.0"),
            "comfort_setpoint_max": _temp_param("26.0"),
        }
    )


@pytest.mark.usefixtures("mock_reduced_setpoint")
@pytest.mark.parametrize(
    ("hvac_mode_int", "current_setpoint", "expected_temperature", "expected_preset"),
    [
        (1, "20.0", 20.0, PRESET_COMFORT),
        (1, "17.0", 17.0, PRESET_ECO),
        # Shifted by a room unit, matches neither comfort nor reduced
        (1, "21.0", 21.0, None),
        # Current setpoint unavailable, falls back to the comfort setpoint
        (1, None, 20.0, None),
        (2, "17.0", 17.0, PRESET_ECO),
        (3, "20.0", 20.0, PRESET_COMFORT),
        (0, "8.0", 8.0, None),
    ],
)
async def test_target_temperature_follows_current_setpoint(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hvac_mode_int: int,
    current_setpoint: str | None,
    expected_temperature: float,
    expected_preset: str | None,
) -> None:
    """Test the target temperature and preset follow the setpoint in effect."""
    mock_bsblan.state.return_value = _circuit_state(hvac_mode_int, current_setpoint)

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["temperature"] == expected_temperature
    assert state.attributes["preset_mode"] == expected_preset


async def test_preset_without_circuit_config(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the eco preset is unknown until the circuit config is fetched."""
    mock_bsblan.state.return_value = _circuit_state(1, "17.0")
    static = mock_bsblan.static_values.return_value
    mock_bsblan.static_values.side_effect = [static, BSBLANError("General error")]

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["temperature"] == 17.0
    assert state.attributes["preset_mode"] is None


async def test_preset_updates_after_slow_fetch(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the eco preset appears once the circuit config is fetched."""
    release = asyncio.Event()
    mock_bsblan.state.return_value = _circuit_state(1, "17.0")
    static = StaticState.model_validate({"temp_reduced_setpoint": _temp_param("17.0")})

    async def _static_values(*args: object, **kwargs: object) -> StaticState:
        if kwargs.get("include") is not None:
            await release.wait()
        return static

    mock_bsblan.static_values.side_effect = _static_values

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["preset_mode"] is None

    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["preset_mode"] == PRESET_ECO


@pytest.mark.usefixtures("mock_reduced_setpoint")
@pytest.mark.parametrize(
    (
        "hvac_mode_int",
        "current_setpoint",
        "temperature",
        "expected_call",
        "expected_static_calls",
    ),
    [
        (3, "20.0", 19.5, {"target_temperature": 19.5}, 2),
        (2, "17.0", 16.5, {"temp_reduced_setpoint": 16.5}, 3),
    ],
    ids=["comfort", "reduced"],
)
async def test_set_temperature_writes_permanent_level(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hvac_mode_int: int,
    current_setpoint: str,
    temperature: float,
    expected_call: dict[str, float],
    expected_static_calls: int,
) -> None:
    """Test setting the temperature in a permanent mode writes its setpoint."""
    mock_bsblan.state.return_value = _circuit_state(hvac_mode_int, current_setpoint)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: temperature},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_bsblan.thermostat.assert_called_once_with(**expected_call, circuit=1)
    # Setup and the first slow refresh fetch the static values; writing the
    # reduced setpoint refreshes the slow coordinator again
    assert mock_bsblan.static_values.call_count == expected_static_calls


@pytest.mark.parametrize(
    ("hvac_mode_int", "service_hvac_mode", "translation_key"),
    [
        (1, None, "set_temperature_in_auto_mode"),
        (3, HVACMode.AUTO, "set_temperature_in_auto_mode"),
        (0, None, "set_temperature_when_off"),
        (3, HVACMode.OFF, "set_temperature_when_off"),
    ],
    ids=["in_auto", "switching_to_auto", "off", "switching_to_off"],
)
async def test_set_temperature_rejected_in_auto_or_off(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hvac_mode_int: int,
    service_hvac_mode: HVACMode | None,
    translation_key: str,
) -> None:
    """Test the target temperature cannot be set in auto or off."""
    mock_bsblan.state.return_value = _circuit_state(hvac_mode_int, "20.0")
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])
    service_data: dict[str, Any] = {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 19.5}
    if service_hvac_mode is not None:
        service_data[ATTR_HVAC_MODE] = service_hvac_mode

    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE, service_data, blocking=True
        )

    assert exc.value.translation_key == translation_key
    mock_bsblan.thermostat.assert_not_called()


@pytest.mark.usefixtures("mock_reduced_setpoint")
@pytest.mark.parametrize(
    ("current_setpoint", "temperature", "preset", "temporary_mode"),
    [
        ("20.0", 20.0, PRESET_COMFORT, 2),
        ("20.0", 17.0, PRESET_ECO, 1),
        # Shifted by a room unit, matches neither comfort nor reduced
        ("21.0", 21.0, PRESET_COMFORT, 2),
    ],
)
async def test_restore_scene_in_auto(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    current_setpoint: str,
    temperature: float,
    preset: str,
    temporary_mode: int,
) -> None:
    """Test restoring a scene in auto only applies its mode and preset."""
    mock_bsblan.state.return_value = _circuit_state(1, current_setpoint)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await async_reproduce_state(
        hass,
        [
            HassState(
                ENTITY_ID,
                HVACMode.AUTO,
                {ATTR_TEMPERATURE: temperature, ATTR_PRESET_MODE: preset},
            )
        ],
    )

    mock_bsblan.thermostat.assert_called_once_with(
        temporary_mode=temporary_mode, circuit=1
    )


@pytest.mark.usefixtures("mock_reduced_setpoint")
@pytest.mark.parametrize(
    "current_setpoint",
    [
        pytest.param("8.0", id="protection_in_effect"),
        # Read before the controller applies the protection setpoint
        pytest.param("20.0", id="previous_setpoint"),
    ],
)
async def test_restore_scene_in_off(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    current_setpoint: str,
) -> None:
    """Test restoring a scene in off keeps the comfort setpoint."""
    mock_bsblan.state.return_value = _circuit_state(0, current_setpoint)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await async_reproduce_state(
        hass, [HassState(ENTITY_ID, HVACMode.OFF, {ATTR_TEMPERATURE: 8.0})]
    )

    mock_bsblan.thermostat.assert_not_called()


@pytest.mark.usefixtures("mock_reduced_setpoint")
async def test_restore_scene_in_permanent_reduced(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test restoring a heat and eco scene in that same state keeps the comfort setpoint."""
    mock_bsblan.state.return_value = _circuit_state(2, "17.0")
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await async_reproduce_state(
        hass,
        [
            HassState(
                ENTITY_ID,
                HVACMode.HEAT,
                {ATTR_TEMPERATURE: 17.0, ATTR_PRESET_MODE: PRESET_ECO},
            )
        ],
    )

    assert mock_bsblan.thermostat.call_args_list == [
        call(temp_reduced_setpoint=17.0, circuit=1),
        call(hvac_mode=2, circuit=1),
    ]


@pytest.mark.usefixtures("mock_reduced_setpoint")
async def test_set_temperature_with_auto_matching_setpoint(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switching to auto with a stored setpoint only switches the mode."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 17.0,
            ATTR_HVAC_MODE: HVACMode.AUTO,
        },
        blocking=True,
    )

    mock_bsblan.thermostat.assert_called_once_with(hvac_mode=1, circuit=1)


async def test_set_temperature_with_hvac_mode(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting the temperature with an HVAC mode writes both."""
    mock_bsblan.state.return_value = _circuit_state(0, None)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 19.5,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )

    assert mock_bsblan.thermostat.call_args_list == [
        call(hvac_mode=3, circuit=1),
        call(target_temperature=19.5, circuit=1),
    ]


@pytest.mark.usefixtures("mock_reduced_setpoint")
@pytest.mark.parametrize(
    ("hvac_mode_int", "current_setpoint", "temperature", "translation_key"),
    [
        # Permanent comfort, below the reduced setpoint (17.0)
        (3, "20.0", 16.5, "comfort_below_reduced"),
        # Permanent reduced, above the comfort setpoint (20.0)
        (2, "17.0", 21.0, "reduced_above_comfort"),
    ],
)
async def test_set_temperature_rejects_setpoint_order(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hvac_mode_int: int,
    current_setpoint: str,
    temperature: float,
    translation_key: str,
) -> None:
    """Test the reduced setpoint cannot end up above the comfort one."""
    mock_bsblan.state.return_value = _circuit_state(hvac_mode_int, current_setpoint)
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: temperature},
            blocking=True,
        )

    assert exc.value.translation_key == translation_key
    mock_bsblan.thermostat.assert_not_called()


@pytest.mark.usefixtures("mock_reduced_setpoint")
async def test_set_temperature_with_heat_writes_comfort(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switching to heat from a reduced period writes the comfort setpoint."""
    mock_bsblan.state.return_value = _circuit_state(1, "17.0")
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 21.0,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )

    assert mock_bsblan.thermostat.call_args_list == [
        call(hvac_mode=3, circuit=1),
        call(target_temperature=21.0, circuit=1),
    ]


async def test_set_data_rereads_only_the_circuit(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a write re-reads only the written circuit."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])
    mock_bsblan.state.reset_mock()
    mock_bsblan.sensor.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 19},
        blocking=True,
    )

    mock_bsblan.state.assert_called_once()
    mock_bsblan.sensor.assert_not_called()


async def test_set_data_ignores_failed_reread(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failed circuit re-read after a write leaves it to the next poll."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])
    mock_bsblan.state.side_effect = BSBLANError("Test error")
    mock_bsblan.sensor.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 19},
        blocking=True,
    )

    mock_bsblan.thermostat.assert_called_once()
    mock_bsblan.sensor.assert_not_called()
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE


async def test_write_keeps_poll_schedule(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a write between two polls does not postpone the next poll."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 19},
        blocking=True,
    )
    mock_bsblan.sensor.reset_mock()

    freezer.tick(timedelta(seconds=7))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_bsblan.sensor.assert_called_once()


async def test_reread_waits_for_running_poll(
    hass: HomeAssistant,
    mock_bsblan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a poll that read the circuit before a write cannot revert it."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])
    old_state = mock_bsblan.state.return_value
    new_state = old_state.model_copy(
        update={"target_temperature": MagicMock(value=19.5)}
    )
    mock_bsblan.state.side_effect = [old_state, new_state]
    release = asyncio.Event()
    sensor = mock_bsblan.sensor.return_value

    async def _blocked_sensor(*args: object, **kwargs: object) -> object:
        await release.wait()
        return sensor

    mock_bsblan.sensor.side_effect = _blocked_sensor

    # The poll reads the circuit, then waits on the sensors
    freezer.tick(timedelta(seconds=12))
    async_fire_time_changed(hass)
    await asyncio.sleep(0)
    write = hass.async_create_task(
        hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 19.5},
            blocking=True,
        )
    )
    await asyncio.sleep(0)
    release.set()
    await write
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes["temperature"] == 19.5
