"""Tests for the Mitsubishi Comfort climate entity."""

from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from mitsubishi_comfort import CommandResult, FanSpeed, Mode, VaneDirection
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.mitsubishi_comfort.const import DEFAULT_SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import _make_device_status

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "climate.living_room"


@pytest.fixture
async def setup_climate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_integration: tuple[AsyncMock, MagicMock],
) -> MagicMock:
    """Set up the integration and return the mock device."""
    _, mock_device = mock_setup_integration
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_device


async def _refresh(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance time past the scan interval to trigger a coordinator refresh."""
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


# -- Snapshot of default state and registry --


async def test_climate_entity(
    hass: HomeAssistant,
    setup_climate: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a climate entity is created for an indoor unit."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


# -- Mode-driven attribute behavior --


@pytest.mark.parametrize(
    ("device_mode", "expected_hvac"),
    [
        ("off", HVACMode.OFF),
        ("heat", HVACMode.HEAT),
        ("dry", HVACMode.DRY),
        ("vent", HVACMode.FAN_ONLY),
        ("auto", HVACMode.HEAT_COOL),
        ("autoCool", HVACMode.HEAT_COOL),
        ("autoHeat", HVACMode.HEAT_COOL),
    ],
)
async def test_hvac_mode_mappings(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
    device_mode: str,
    expected_hvac: HVACMode,
) -> None:
    """Test HVAC mode mappings from device mode strings."""
    setup_climate.status = _make_device_status(mode=device_mode)
    await _refresh(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == expected_hvac


async def test_hvac_mode_unknown_when_no_mode(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test entity reports unknown when device has no mode."""
    setup_climate.status = _make_device_status(mode=None)
    await _refresh(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("device_mode", "standby", "expected_action"),
    [
        ("off", False, HVACAction.OFF),
        ("heat", False, HVACAction.HEATING),
        ("dry", False, HVACAction.DRYING),
        ("vent", False, HVACAction.FAN),
        ("auto", False, HVACAction.IDLE),
        ("autoCool", False, HVACAction.COOLING),
        ("autoHeat", False, HVACAction.HEATING),
        ("cool", True, HVACAction.IDLE),
    ],
)
async def test_hvac_action(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
    device_mode: str,
    standby: bool,
    expected_action: HVACAction,
) -> None:
    """Test HVAC action mappings for all modes and standby."""
    setup_climate.status = _make_device_status(mode=device_mode, standby=standby)
    await _refresh(hass, freezer)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_HVAC_ACTION] is expected_action


async def test_hvac_action_unknown_when_no_mode(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test HVAC action is None when device has no mode."""
    setup_climate.status = _make_device_status(mode=None)
    await _refresh(hass, freezer)

    assert hass.states.get(ENTITY_ID).attributes.get(ATTR_HVAC_ACTION) is None


@pytest.mark.parametrize(
    ("device_mode", "expected_temp"),
    [
        ("heat", 21.0),
        ("autoCool", 24.0),
        ("autoHeat", 21.0),
    ],
)
async def test_target_temperature(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
    device_mode: str,
    expected_temp: float,
) -> None:
    """Test target temperature follows the active mode's setpoint."""
    setup_climate.status = _make_device_status(mode=device_mode)
    await _refresh(hass, freezer)

    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == expected_temp


async def test_target_temperature_none_in_dry_mode(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test target temperature is None in dry mode."""
    setup_climate.status = _make_device_status(mode="dry")
    await _refresh(hass, freezer)

    assert hass.states.get(ENTITY_ID).attributes.get(ATTR_TEMPERATURE) is None


async def test_target_temperature_high_low_auto(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test target_temperature_high/low track setpoints in auto mode."""
    setup_climate.status = _make_device_status(mode="auto")
    await _refresh(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 24.0
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 21.0


# -- Min/max temperature behavior --


@pytest.mark.parametrize(
    ("device_mode", "expected_min", "expected_max"),
    [
        ("cool", 18.0, 30.0),
        ("heat", 16.0, 28.0),
    ],
)
async def test_min_max_temp(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
    device_mode: str,
    expected_min: float,
    expected_max: float,
) -> None:
    """Test min/max temp track the active mode's setpoint bounds."""
    setup_climate.status = _make_device_status(mode=device_mode)
    await _refresh(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MIN_TEMP] == expected_min
    assert state.attributes[ATTR_MAX_TEMP] == expected_max


async def test_min_max_temp_fallback_when_none(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test min/max temp fall back to climate defaults when setpoints are None."""
    setup_climate.status = _make_device_status(
        min_cool_setpoint=None,
        max_cool_setpoint=None,
        min_heat_setpoint=None,
        max_heat_setpoint=None,
    )
    await _refresh(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MIN_TEMP] == 7
    assert state.attributes[ATTR_MAX_TEMP] == 35


async def test_min_max_temp_heat_falls_back_to_cool(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test min/max temp in heat mode fall back to cool setpoints when heat is None."""
    setup_climate.status = _make_device_status(
        mode="heat",
        min_heat_setpoint=None,
        max_heat_setpoint=None,
    )
    await _refresh(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_MIN_TEMP] == 18.0
    assert state.attributes[ATTR_MAX_TEMP] == 30.0


# -- Supported features --


async def test_supported_features_no_auto(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test supported features without auto mode lack temp range."""
    setup_climate.supported_modes = [Mode.OFF, Mode.COOL, Mode.HEAT]
    await _refresh(hass, freezer)

    features = hass.states.get(ENTITY_ID).attributes[ATTR_SUPPORTED_FEATURES]
    assert features & ClimateEntityFeature.TARGET_TEMPERATURE
    assert not (features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE)


async def test_supported_features_no_vane(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test supported features without vane directions lack swing mode."""
    setup_climate.supported_vane_directions = []
    await _refresh(hass, freezer)

    features = hass.states.get(ENTITY_ID).attributes[ATTR_SUPPORTED_FEATURES]
    assert not (features & ClimateEntityFeature.SWING_MODE)


# -- Service calls --


async def test_set_hvac_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting HVAC mode via service call updates device and state."""
    device = setup_climate
    device.set_mode = AsyncMock(return_value=CommandResult(success=True, value="heat"))

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    device.set_mode.assert_awaited_once_with(Mode.HEAT)
    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT


async def test_set_hvac_mode_failed_keeps_state(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test failed set_hvac_mode does not change reported state."""
    device = setup_climate
    device.set_mode = AsyncMock(return_value=CommandResult(success=False))

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).state == HVACMode.COOL


async def test_set_hvac_mode_unmapped_returns(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting an unmapped HVACMode does not call the device."""
    device = setup_climate

    with patch.dict(
        "homeassistant.components.mitsubishi_comfort.climate._HVAC_TO_MODE",
        {HVACMode.COOL: Mode.COOL},
        clear=True,
    ):
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        )

    device.set_mode.assert_not_awaited()


async def test_set_temperature_cool_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting temperature in cool mode updates the cool setpoint."""
    device = setup_climate
    device.set_cool_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=22.0)
    )

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.0},
        blocking=True,
    )

    device.set_cool_setpoint.assert_awaited_once_with(22.0)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 22.0


async def test_set_temperature_heat_mode(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test setting temperature in heat mode updates the heat setpoint."""
    device = setup_climate
    device.status = _make_device_status(mode="heat")
    await _refresh(hass, freezer)
    device.set_heat_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=20.0)
    )

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 20.0},
        blocking=True,
    )

    device.set_heat_setpoint.assert_awaited_once_with(20.0)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 20.0


async def test_set_temperature_high_low(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test setting high and low temperatures in auto mode."""
    device = setup_climate
    device.status = _make_device_status(mode="auto")
    await _refresh(hass, freezer)
    device.set_cool_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=25.0)
    )
    device.set_heat_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=19.0)
    )

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TARGET_TEMP_HIGH: 25.0,
            ATTR_TARGET_TEMP_LOW: 19.0,
        },
        blocking=True,
    )

    device.set_cool_setpoint.assert_awaited_once_with(25.0)
    device.set_heat_setpoint.assert_awaited_once_with(19.0)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 25.0
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 19.0


async def test_set_temperature_failed_keeps_state(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test failed set_temperature does not change reported setpoint."""
    device = setup_climate
    device.set_cool_setpoint = AsyncMock(return_value=CommandResult(success=False))

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.0},
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 24.0


@pytest.mark.parametrize(
    ("device_mode", "set_method"),
    [
        ("autoCool", "set_cool_setpoint"),
        ("autoHeat", "set_heat_setpoint"),
    ],
)
async def test_set_temperature_in_auto_mode(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
    device_mode: str,
    set_method: str,
) -> None:
    """Test set_temperature in autoCool/autoHeat targets the right setpoint."""
    device = setup_climate
    device.status = _make_device_status(mode=device_mode)
    await _refresh(hass, freezer)
    setattr(
        device,
        set_method,
        AsyncMock(return_value=CommandResult(success=True, value=22.0)),
    )

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.0},
        blocking=True,
    )

    getattr(device, set_method).assert_awaited_once_with(22.0)


async def test_set_fan_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting fan mode via service call updates device and state."""
    device = setup_climate
    device.set_fan_speed = AsyncMock(
        return_value=CommandResult(success=True, value="quiet")
    )

    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "quiet"},
        blocking=True,
    )

    device.set_fan_speed.assert_awaited_once_with(FanSpeed.QUIET)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_FAN_MODE] == "quiet"


async def test_set_fan_mode_unknown(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting an unknown fan mode raises ServiceValidationError."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "climate",
            "set_fan_mode",
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "turbo"},
            blocking=True,
        )


async def test_set_fan_mode_failed_keeps_state(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test failed set_fan_mode does not change reported fan mode."""
    device = setup_climate
    device.set_fan_speed = AsyncMock(return_value=CommandResult(success=False))

    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "quiet"},
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).attributes[ATTR_FAN_MODE] == "auto"


async def test_set_swing_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting swing mode via service call updates device and state."""
    device = setup_climate
    device.set_vane_direction = AsyncMock(
        return_value=CommandResult(success=True, value="swing")
    )

    await hass.services.async_call(
        "climate",
        "set_swing_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: "swing"},
        blocking=True,
    )

    device.set_vane_direction.assert_awaited_once_with(VaneDirection.SWING)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_SWING_MODE] == "swing"


async def test_set_swing_mode_unknown(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting an unknown swing mode raises ServiceValidationError."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "climate",
            "set_swing_mode",
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: "unknown_direction"},
            blocking=True,
        )


async def test_set_swing_mode_failed_keeps_state(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test failed set_swing_mode does not change reported swing mode."""
    device = setup_climate
    device.set_vane_direction = AsyncMock(return_value=CommandResult(success=False))

    await hass.services.async_call(
        "climate",
        "set_swing_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: "swing"},
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).attributes[ATTR_SWING_MODE] == "auto"


async def test_turn_off(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test turning off the entity via service call."""
    device = setup_climate
    device.set_mode = AsyncMock(return_value=CommandResult(success=True, value="off"))

    await hass.services.async_call(
        "climate",
        "turn_off",
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    device.set_mode.assert_awaited_once_with(Mode.OFF)
    assert hass.states.get(ENTITY_ID).state == HVACMode.OFF


# -- Optimistic state cleared on next refresh --


async def test_optimistic_mode_cleared_on_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test optimistic mode is cleared when a fresh device status arrives."""
    device = setup_climate
    device.set_mode = AsyncMock(return_value=CommandResult(success=True, value="heat"))

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == HVACMode.HEAT

    await _refresh(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == HVACMode.COOL


async def test_optimistic_setpoint_cleared_on_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test optimistic setpoint is cleared when a fresh device status arrives."""
    device = setup_climate
    device.set_cool_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=22.0)
    )

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.0},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 22.0

    await _refresh(hass, freezer)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 24.0


async def test_optimistic_fan_speed_cleared_on_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test optimistic fan speed is cleared when a fresh device status arrives."""
    device = setup_climate
    device.set_fan_speed = AsyncMock(
        return_value=CommandResult(success=True, value="quiet")
    )

    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "quiet"},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_FAN_MODE] == "quiet"

    await _refresh(hass, freezer)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_FAN_MODE] == "auto"


async def test_optimistic_swing_cleared_on_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test optimistic swing mode is cleared when a fresh device status arrives."""
    device = setup_climate
    device.set_vane_direction = AsyncMock(
        return_value=CommandResult(success=True, value="swing")
    )

    await hass.services.async_call(
        "climate",
        "set_swing_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: "swing"},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).attributes[ATTR_SWING_MODE] == "swing"

    await _refresh(hass, freezer)
    assert hass.states.get(ENTITY_ID).attributes[ATTR_SWING_MODE] == "auto"


async def test_optimistic_temp_high_low_in_auto(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test optimistic high/low setpoints reflect immediately in auto mode."""
    device = setup_climate
    device.status = _make_device_status(mode="auto")
    await _refresh(hass, freezer)
    device.set_cool_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=26.0)
    )
    device.set_heat_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=18.0)
    )

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TARGET_TEMP_HIGH: 26.0,
            ATTR_TARGET_TEMP_LOW: 18.0,
        },
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 26.0
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 18.0


# -- Coordinator availability --


async def test_coordinator_update_failure_makes_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test that a failed coordinator update makes the entity unavailable."""
    setup_climate.update_status = AsyncMock(return_value=False)
    await _refresh(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_coordinator_update_exception_makes_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test that an exception during update makes the entity unavailable."""
    setup_climate.update_status = AsyncMock(side_effect=TimeoutError("timeout"))
    await _refresh(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_coordinator_recovery_restores_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_climate: MagicMock,
) -> None:
    """Test that a successful update after failure restores availability."""
    setup_climate.update_status = AsyncMock(return_value=False)
    await _refresh(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    setup_climate.update_status = AsyncMock(return_value=True)
    await _refresh(hass, freezer)
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE
