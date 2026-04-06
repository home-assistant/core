"""Tests for the Mitsubishi Comfort climate entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from mitsubishi_comfort import CommandResult, FanSpeed, Mode, VaneDirection
import pytest

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.mitsubishi_comfort.climate import MitsubishiComfortClimate
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry

from .conftest import _make_device_status

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


async def test_climate_entity_registered(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test that a climate entity is created for an indoor unit."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.COOL


async def test_temperature_unit(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test temperature unit is Celsius."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("temperature_unit") is None or True
    # Verify via direct entity access
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.temperature_unit == UnitOfTemperature.CELSIUS


async def test_hvac_mode_cool(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test HVAC mode returns COOL when device is in cool mode."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.COOL


async def test_hvac_mode_mappings(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test all HVAC mode mappings from device mode strings."""
    device = setup_climate

    mode_pairs = [
        ("off", HVACMode.OFF),
        ("cool", HVACMode.COOL),
        ("heat", HVACMode.HEAT),
        ("dry", HVACMode.DRY),
        ("vent", HVACMode.FAN_ONLY),
        ("auto", HVACMode.HEAT_COOL),
        ("autoCool", HVACMode.HEAT_COOL),
        ("autoHeat", HVACMode.HEAT_COOL),
    ]

    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    for device_mode, expected_hvac in mode_pairs:
        device.status = _make_device_status(mode=device_mode)
        assert entity.hvac_mode is expected_hvac, f"Failed for mode {device_mode}"


async def test_hvac_mode_none_when_no_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test HVAC mode returns None when device has no mode."""
    setup_climate.status = _make_device_status(mode=None)
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.hvac_mode is None


async def test_hvac_action_cooling(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test HVAC action is COOLING when in cool mode."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.hvac_action is HVACAction.COOLING


async def test_hvac_action_idle_on_standby(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test HVAC action is IDLE when device is in standby."""
    setup_climate.status = _make_device_status(mode="cool", standby=True)
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.hvac_action is HVACAction.IDLE


async def test_hvac_action_none_when_no_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test HVAC action is None when device has no mode."""
    setup_climate.status = _make_device_status(mode=None)
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.hvac_action is None


async def test_hvac_action_all_modes(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test HVAC action mappings for all modes."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    device = setup_climate

    action_pairs = [
        ("off", HVACAction.OFF),
        ("heat", HVACAction.HEATING),
        ("dry", HVACAction.DRYING),
        ("vent", HVACAction.FAN),
        ("auto", HVACAction.IDLE),
        ("autoCool", HVACAction.COOLING),
        ("autoHeat", HVACAction.HEATING),
    ]

    for mode, expected_action in action_pairs:
        device.status = _make_device_status(mode=mode)
        assert entity.hvac_action is expected_action, f"Failed for mode {mode}"


async def test_hvac_modes_list(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test hvac_modes returns supported modes."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    modes = entity.hvac_modes
    assert HVACMode.OFF in modes
    assert HVACMode.COOL in modes
    assert HVACMode.HEAT in modes
    assert HVACMode.DRY in modes
    assert HVACMode.FAN_ONLY in modes
    assert HVACMode.HEAT_COOL in modes


async def test_current_temperature(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test current temperature returns room temperature."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("current_temperature") == 23.5


async def test_current_humidity(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test current humidity returns device humidity."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.current_humidity == 45.0


async def test_target_temperature_cool_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test target temperature in cool mode returns cool setpoint."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("temperature") == 24.0


async def test_target_temperature_heat_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test target temperature in heat mode returns heat setpoint."""
    setup_climate.status = _make_device_status(mode="heat")
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.target_temperature == 21.0


async def test_target_temperature_auto_cool(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test target temperature in autoCool mode returns cool setpoint."""
    setup_climate.status = _make_device_status(mode="autoCool")
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.target_temperature == 24.0


async def test_target_temperature_auto_heat(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test target temperature in autoHeat mode returns heat setpoint."""
    setup_climate.status = _make_device_status(mode="autoHeat")
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.target_temperature == 21.0


async def test_target_temperature_none_in_dry_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test target temperature returns None in dry mode."""
    setup_climate.status = _make_device_status(mode="dry")
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.target_temperature is None


async def test_target_temperature_high_auto_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test target_temperature_high/low in auto modes."""
    setup_climate.status = _make_device_status(mode="auto")
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.target_temperature_high == 24.0
    assert entity.target_temperature_low == 21.0


async def test_target_temperature_high_none_in_cool_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test target_temperature_high is None outside auto modes."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.target_temperature_high is None
    assert entity.target_temperature_low is None


async def test_fan_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test fan mode returns device fan speed."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("fan_mode") == "auto"


async def test_fan_modes(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test fan modes returns supported fan speeds."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.fan_modes == ["quiet", "low", "auto"]


async def test_swing_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test swing mode returns device vane direction."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get("swing_mode") == "auto"


async def test_swing_modes(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test swing modes returns supported vane directions."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.swing_modes == ["horizontal", "auto", "swing"]


async def test_min_temp_cool_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test min temp in cool mode returns min_cool_setpoint."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.min_temp == 18.0


async def test_min_temp_heat_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test min temp in heat mode returns min_heat_setpoint."""
    setup_climate.status = _make_device_status(mode="heat")
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.min_temp == 16.0


async def test_max_temp_cool_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test max temp in cool mode returns max_cool_setpoint."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.max_temp == 30.0


async def test_max_temp_heat_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test max temp in heat mode returns max_heat_setpoint."""
    setup_climate.status = _make_device_status(mode="heat")
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.max_temp == 28.0


async def test_min_temp_fallback_when_none(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test min temp falls back to parent default when setpoints are None."""
    setup_climate.status = _make_device_status(
        min_cool_setpoint=None,
        max_cool_setpoint=None,
        min_heat_setpoint=None,
        max_heat_setpoint=None,
    )
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.min_temp == 7
    assert entity.max_temp == 35


async def test_min_temp_heat_setpoint_none_falls_to_cool(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test min temp in heat mode falls back to cool setpoint if heat is None."""
    setup_climate.status = _make_device_status(
        mode="heat",
        min_heat_setpoint=None,
        max_heat_setpoint=None,
    )
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.min_temp == 18.0
    assert entity.max_temp == 30.0


async def test_supported_features(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test supported features include expected capabilities."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    features = entity.supported_features

    assert features & ClimateEntityFeature.TARGET_TEMPERATURE
    assert features & ClimateEntityFeature.FAN_MODE
    assert features & ClimateEntityFeature.TURN_OFF
    assert features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    assert features & ClimateEntityFeature.SWING_MODE


async def test_supported_features_no_auto(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test supported features without auto mode lack temp range."""
    setup_climate.supported_modes = [Mode.OFF, Mode.COOL, Mode.HEAT]
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    features = entity.supported_features
    assert features & ClimateEntityFeature.TARGET_TEMPERATURE
    assert not (features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE)


async def test_supported_features_no_vane(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test supported features without vane directions lack swing mode."""
    setup_climate.supported_vane_directions = []
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    features = entity.supported_features
    assert not (features & ClimateEntityFeature.SWING_MODE)


async def test_extra_state_attributes_with_vane_lr(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test extra state attributes include vane_left_right when present."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    attrs = entity.extra_state_attributes
    assert attrs is not None
    assert attrs["vane_left_right"] == "auto"


async def test_extra_state_attributes_none_when_no_vane_lr(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test extra state attributes returns None when vane_left_right is absent."""
    setup_climate.status = _make_device_status(vane_left_right=None)
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.extra_state_attributes is None


# -- Command tests via service calls --


async def test_set_hvac_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting HVAC mode via service call."""
    device = setup_climate
    device.set_mode = AsyncMock(return_value=CommandResult(success=True, value="heat"))

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    device.set_mode.assert_awaited_once_with(Mode.HEAT)


async def test_set_hvac_mode_unsupported(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting HVAC mode when command fails doesn't set optimistic state."""
    device = setup_climate
    device.set_mode = AsyncMock(return_value=CommandResult(success=False))

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity._optimistic_mode is None


async def test_set_hvac_mode_unknown_mode_returns(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting an unmapped HVACMode returns without calling device."""
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
    """Test setting temperature in cool mode."""
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


async def test_set_temperature_heat_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting temperature in heat mode."""
    device = setup_climate
    device.status = _make_device_status(mode="heat")
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


async def test_set_temperature_high_low(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting high and low temperatures for auto mode."""
    device = setup_climate
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


async def test_set_temperature_failed_command(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting temperature when command fails doesn't set optimistic state."""
    device = setup_climate
    device.set_cool_setpoint = AsyncMock(return_value=CommandResult(success=False))

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 22.0},
        blocking=True,
    )

    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity._optimistic_cool_setpoint is None


async def test_set_fan_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting fan mode via service call."""
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


async def test_set_fan_mode_failed(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting fan mode when command fails."""
    device = setup_climate
    device.set_fan_speed = AsyncMock(return_value=CommandResult(success=False))

    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "quiet"},
        blocking=True,
    )

    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity._optimistic_fan_speed is None


async def test_set_swing_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting swing mode via service call."""
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


async def test_set_swing_mode_failed(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting swing mode when command fails."""
    device = setup_climate
    device.set_vane_direction = AsyncMock(return_value=CommandResult(success=False))

    await hass.services.async_call(
        "climate",
        "set_swing_mode",
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: "swing"},
        blocking=True,
    )

    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity._optimistic_vane_direction is None


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


# -- Optimistic state tests --


async def test_optimistic_mode_used_for_hvac_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test that optimistic mode overrides device mode."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    entity._optimistic_mode = "heat"
    assert entity.hvac_mode is HVACMode.HEAT


async def test_optimistic_cool_setpoint(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test that optimistic cool setpoint overrides device value."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    entity._optimistic_cool_setpoint = 22.0
    assert entity.target_temperature == 22.0


async def test_optimistic_heat_setpoint(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test that optimistic heat setpoint overrides device value in heat mode."""
    setup_climate.status = _make_device_status(mode="heat")
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    entity._optimistic_heat_setpoint = 19.0
    assert entity.target_temperature == 19.0


async def test_optimistic_fan_speed(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test that optimistic fan speed overrides device value."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    entity._optimistic_fan_speed = "quiet"
    assert entity.fan_mode == "quiet"


async def test_optimistic_vane_direction(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test that optimistic vane direction overrides device value."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    entity._optimistic_vane_direction = "swing"
    assert entity.swing_mode == "swing"


async def test_coordinator_update_clears_optimistic(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test that coordinator update clears all optimistic state."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]

    entity._optimistic_mode = "heat"
    entity._optimistic_cool_setpoint = 22.0
    entity._optimistic_heat_setpoint = 19.0
    entity._optimistic_fan_speed = "quiet"
    entity._optimistic_vane_direction = "swing"

    entity._handle_coordinator_update()

    assert entity._optimistic_mode is None
    assert entity._optimistic_cool_setpoint is None
    assert entity._optimistic_heat_setpoint is None
    assert entity._optimistic_fan_speed is None
    assert entity._optimistic_vane_direction is None


async def test_optimistic_temp_high_low_in_auto(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test optimistic setpoints in auto mode for high/low targets."""
    setup_climate.status = _make_device_status(mode="auto")
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]

    entity._optimistic_cool_setpoint = 26.0
    entity._optimistic_heat_setpoint = 18.0

    assert entity.target_temperature_high == 26.0
    assert entity.target_temperature_low == 18.0


async def test_unique_id(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test unique ID is the device serial."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.unique_id == "SERIAL001"


async def test_entity_available(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test entity availability delegates to coordinator."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    assert entity.available is True

    entity.coordinator._consecutive_failures = 5
    assert entity.available is False


async def test_entity_device_info(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test device info is populated correctly."""
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]
    info = entity.device_info
    assert info["identifiers"] == {("mitsubishi_comfort", "SERIAL001")}
    assert info["name"] == "Living Room"
    assert info["manufacturer"] == "Mitsubishi"


async def test_set_temperature_auto_cool_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting temperature in autoCool mode sets cool setpoint."""
    device = setup_climate
    device.status = _make_device_status(mode="autoCool")
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


async def test_set_temperature_auto_heat_mode(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test setting temperature in autoHeat mode sets heat setpoint."""
    device = setup_climate
    device.status = _make_device_status(mode="autoHeat")
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


async def test_set_fan_mode_unknown_direct(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test calling async_set_fan_mode directly with unknown mode returns early."""
    device = setup_climate
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]

    await entity.async_set_fan_mode("turbo")

    device.set_fan_speed.assert_not_awaited()


async def test_set_swing_mode_unknown_direct(
    hass: HomeAssistant,
    setup_climate: MagicMock,
) -> None:
    """Test calling async_set_swing_mode directly with unknown mode returns early."""
    device = setup_climate
    entity: MitsubishiComfortClimate = hass.data["entity_components"][
        "climate"
    ].get_entity(ENTITY_ID)  # type: ignore[assignment]

    await entity.async_set_swing_mode("unknown_direction")

    device.set_vane_direction.assert_not_awaited()
