"""Tests for the Mitsubishi Comfort climate entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from mitsubishi_comfort import (
    CommandResult,
    DeviceStatus,
    FanSpeed,
    IndoorUnit,
    Mode,
    VaneDirection,
)

from homeassistant.components.climate import ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.components.mitsubishi_comfort.climate import (
    MitsubishiComfortClimate,
    async_setup_entry,
)
from homeassistant.components.mitsubishi_comfort.coordinator import (
    MitsubishiComfortCoordinator,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant


def _make_mock_device(status: DeviceStatus | None = None) -> MagicMock:
    """Create a mock IndoorUnit with realistic attributes."""
    device = MagicMock()
    device.serial = "SERIAL001"
    device.name = "Living Room"
    device.update_status = AsyncMock(return_value=True)
    device.close = AsyncMock()

    if status is None:
        status = DeviceStatus(
            mode="cool",
            standby=False,
            heat_setpoint=21.0,
            cool_setpoint=24.0,
            room_temperature=23.5,
            fan_speed="auto",
            vane_direction="auto",
            filter_dirty=False,
            defrost=False,
            current_humidity=45.0,
            outdoor_temperature=30.0,
            wifi_rssi=-55,
            sensor_battery=80,
            sensor_rssi=-60,
            run_state="on",
            vane_left_right="auto",
            uptime=86400,
            firmware_version="2.1.0",
            hardware_version="1.0.0",
            min_cool_setpoint=18.0,
            max_cool_setpoint=30.0,
            min_heat_setpoint=16.0,
            max_heat_setpoint=28.0,
        )

    device.status = status
    device.supported_modes = [
        Mode.OFF,
        Mode.COOL,
        Mode.HEAT,
        Mode.DRY,
        Mode.FAN,
        Mode.AUTO,
    ]
    device.supported_fan_speeds = [FanSpeed.QUIET, FanSpeed.LOW, FanSpeed.AUTO]
    device.supported_vane_directions = [
        VaneDirection.HORIZONTAL,
        VaneDirection.AUTO,
        VaneDirection.SWING,
    ]

    device.set_mode = AsyncMock(return_value=CommandResult(success=True, value="cool"))
    device.set_cool_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=24.0)
    )
    device.set_heat_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=21.0)
    )
    device.set_fan_speed = AsyncMock(
        return_value=CommandResult(success=True, value="auto")
    )
    device.set_vane_direction = AsyncMock(
        return_value=CommandResult(success=True, value="auto")
    )

    return device


def _make_coordinator_and_entity(
    hass: HomeAssistant, device: MagicMock | None = None
) -> tuple[MitsubishiComfortCoordinator, MitsubishiComfortClimate]:
    """Create a coordinator and climate entity with mock device."""
    if device is None:
        device = _make_mock_device()

    coordinator = MitsubishiComfortCoordinator(hass, device)
    entity = MitsubishiComfortClimate(coordinator)
    return coordinator, entity


async def test_temperature_unit(hass: HomeAssistant) -> None:
    """Test temperature unit is Celsius."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity.temperature_unit == UnitOfTemperature.CELSIUS


async def test_hvac_mode_cool(hass: HomeAssistant) -> None:
    """Test HVAC mode returns COOL when device is in cool mode."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity.hvac_mode is HVACMode.COOL


async def test_hvac_mode_mappings(hass: HomeAssistant) -> None:
    """Test all HVAC mode mappings from device mode strings."""
    device = _make_mock_device()
    _, entity = _make_coordinator_and_entity(hass, device)

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

    for device_mode, expected_hvac in mode_pairs:
        device.status = DeviceStatus(
            mode=device_mode,
            standby=False,
            heat_setpoint=21.0,
            cool_setpoint=24.0,
            room_temperature=23.5,
            fan_speed="auto",
            vane_direction="auto",
            filter_dirty=False,
            defrost=False,
            current_humidity=None,
            outdoor_temperature=None,
            wifi_rssi=None,
            sensor_battery=None,
            sensor_rssi=None,
            run_state="on",
            vane_left_right=None,
            uptime=None,
            firmware_version=None,
            hardware_version=None,
            min_cool_setpoint=18.0,
            max_cool_setpoint=30.0,
            min_heat_setpoint=16.0,
            max_heat_setpoint=28.0,
        )
        assert entity.hvac_mode is expected_hvac, f"Failed for mode {device_mode}"


async def test_hvac_mode_none_when_no_mode(hass: HomeAssistant) -> None:
    """Test HVAC mode returns None when device has no mode."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode=None,
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state=None,
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=None,
        max_cool_setpoint=None,
        min_heat_setpoint=None,
        max_heat_setpoint=None,
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    assert entity.hvac_mode is None


async def test_hvac_action_cooling(hass: HomeAssistant) -> None:
    """Test HVAC action is COOLING when in cool mode."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity.hvac_action is HVACAction.COOLING


async def test_hvac_action_idle_on_standby(hass: HomeAssistant) -> None:
    """Test HVAC action is IDLE when device is in standby."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="cool",
        standby=True,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    assert entity.hvac_action is HVACAction.IDLE


async def test_hvac_action_none_when_no_mode(hass: HomeAssistant) -> None:
    """Test HVAC action is None when device has no mode."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode=None,
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state=None,
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=None,
        max_cool_setpoint=None,
        min_heat_setpoint=None,
        max_heat_setpoint=None,
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    assert entity.hvac_action is None


async def test_hvac_action_all_modes(hass: HomeAssistant) -> None:
    """Test HVAC action mappings for all modes."""
    device = _make_mock_device()
    _, entity = _make_coordinator_and_entity(hass, device)

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
        device.status = DeviceStatus(
            mode=mode,
            standby=False,
            heat_setpoint=21.0,
            cool_setpoint=24.0,
            room_temperature=23.5,
            fan_speed="auto",
            vane_direction="auto",
            filter_dirty=False,
            defrost=False,
            current_humidity=None,
            outdoor_temperature=None,
            wifi_rssi=None,
            sensor_battery=None,
            sensor_rssi=None,
            run_state="on",
            vane_left_right=None,
            uptime=None,
            firmware_version=None,
            hardware_version=None,
            min_cool_setpoint=18.0,
            max_cool_setpoint=30.0,
            min_heat_setpoint=16.0,
            max_heat_setpoint=28.0,
        )
        assert entity.hvac_action is expected_action, f"Failed for mode {mode}"


async def test_hvac_modes_list(hass: HomeAssistant) -> None:
    """Test hvac_modes returns supported modes."""
    _, entity = _make_coordinator_and_entity(hass)
    modes = entity.hvac_modes
    assert HVACMode.OFF in modes
    assert HVACMode.COOL in modes
    assert HVACMode.HEAT in modes
    assert HVACMode.DRY in modes
    assert HVACMode.FAN_ONLY in modes
    assert HVACMode.HEAT_COOL in modes


async def test_current_temperature(hass: HomeAssistant) -> None:
    """Test current temperature returns room temperature."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity.current_temperature == 23.5


async def test_current_humidity(hass: HomeAssistant) -> None:
    """Test current humidity returns device humidity."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity.current_humidity == 45.0


async def test_target_temperature_cool_mode(hass: HomeAssistant) -> None:
    """Test target temperature in cool mode returns cool setpoint."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity.target_temperature == 24.0


async def test_target_temperature_heat_mode(hass: HomeAssistant) -> None:
    """Test target temperature in heat mode returns heat setpoint."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="heat",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    assert entity.target_temperature == 21.0


async def test_target_temperature_auto_cool(hass: HomeAssistant) -> None:
    """Test target temperature in autoCool mode returns cool setpoint."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="autoCool",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    assert entity.target_temperature == 24.0


async def test_target_temperature_auto_heat(hass: HomeAssistant) -> None:
    """Test target temperature in autoHeat mode returns heat setpoint."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="autoHeat",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    assert entity.target_temperature == 21.0


async def test_target_temperature_none_in_dry_mode(hass: HomeAssistant) -> None:
    """Test target temperature returns None in dry mode."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="dry",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    assert entity.target_temperature is None


async def test_target_temperature_high_auto_mode(hass: HomeAssistant) -> None:
    """Test target_temperature_high in auto modes returns cool setpoint."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="auto",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    assert entity.target_temperature_high == 24.0
    assert entity.target_temperature_low == 21.0


async def test_target_temperature_high_none_in_cool_mode(
    hass: HomeAssistant,
) -> None:
    """Test target_temperature_high is None outside auto modes."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity.target_temperature_high is None
    assert entity.target_temperature_low is None


async def test_fan_mode(hass: HomeAssistant) -> None:
    """Test fan mode returns device fan speed."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity.fan_mode == "auto"


async def test_fan_modes(hass: HomeAssistant) -> None:
    """Test fan modes returns supported fan speeds."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity.fan_modes == ["quiet", "low", "auto"]


async def test_swing_mode(hass: HomeAssistant) -> None:
    """Test swing mode returns device vane direction."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity.swing_mode == "auto"


async def test_swing_modes(hass: HomeAssistant) -> None:
    """Test swing modes returns supported vane directions."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity.swing_modes == ["horizontal", "auto", "swing"]


async def test_min_temp_cool_mode(hass: HomeAssistant) -> None:
    """Test min temp in cool mode returns min_cool_setpoint."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity.min_temp == 18.0


async def test_min_temp_heat_mode(hass: HomeAssistant) -> None:
    """Test min temp in heat mode returns min_heat_setpoint."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="heat",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    assert entity.min_temp == 16.0


async def test_max_temp_cool_mode(hass: HomeAssistant) -> None:
    """Test max temp in cool mode returns max_cool_setpoint."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity.max_temp == 30.0


async def test_max_temp_heat_mode(hass: HomeAssistant) -> None:
    """Test max temp in heat mode returns max_heat_setpoint."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="heat",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    assert entity.max_temp == 28.0


async def test_min_temp_fallback_when_none(hass: HomeAssistant) -> None:
    """Test min temp falls back to parent default when setpoints are None."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="cool",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=None,
        max_cool_setpoint=None,
        min_heat_setpoint=None,
        max_heat_setpoint=None,
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    # Falls back to ClimateEntity default (7)
    assert entity.min_temp == 7
    assert entity.max_temp == 35


async def test_min_temp_heat_setpoint_none_falls_to_cool(
    hass: HomeAssistant,
) -> None:
    """Test min temp in heat mode falls back to cool setpoint if heat is None."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="heat",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=None,
        max_heat_setpoint=None,
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    assert entity.min_temp == 18.0
    assert entity.max_temp == 30.0


async def test_supported_features(hass: HomeAssistant) -> None:
    """Test supported features include expected capabilities."""
    _, entity = _make_coordinator_and_entity(hass)
    features = entity.supported_features

    assert features & ClimateEntityFeature.TARGET_TEMPERATURE
    assert features & ClimateEntityFeature.FAN_MODE
    assert features & ClimateEntityFeature.TURN_OFF
    assert features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    assert features & ClimateEntityFeature.SWING_MODE


async def test_supported_features_no_auto(hass: HomeAssistant) -> None:
    """Test supported features without auto mode lack temp range."""
    device = _make_mock_device()
    device.supported_modes = [Mode.OFF, Mode.COOL, Mode.HEAT]
    _, entity = _make_coordinator_and_entity(hass, device)
    features = entity.supported_features

    assert features & ClimateEntityFeature.TARGET_TEMPERATURE
    assert not (features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE)


async def test_supported_features_no_vane(hass: HomeAssistant) -> None:
    """Test supported features without vane directions lack swing mode."""
    device = _make_mock_device()
    device.supported_vane_directions = []
    _, entity = _make_coordinator_and_entity(hass, device)
    features = entity.supported_features

    assert not (features & ClimateEntityFeature.SWING_MODE)


async def test_extra_state_attributes_with_vane_lr(hass: HomeAssistant) -> None:
    """Test extra state attributes include vane_left_right when present."""
    _, entity = _make_coordinator_and_entity(hass)
    attrs = entity.extra_state_attributes
    assert attrs is not None
    assert attrs["vane_left_right"] == "auto"


async def test_extra_state_attributes_none_when_no_vane_lr(
    hass: HomeAssistant,
) -> None:
    """Test extra state attributes returns None when vane_left_right is absent."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="cool",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    assert entity.extra_state_attributes is None


# -- Command tests --


async def test_set_hvac_mode(hass: HomeAssistant) -> None:
    """Test setting HVAC mode sends command and sets optimistic state."""
    device = _make_mock_device()
    device.set_mode = AsyncMock(return_value=CommandResult(success=True, value="heat"))
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_hvac_mode(HVACMode.HEAT)

    device.set_mode.assert_awaited_once_with(Mode.HEAT)
    assert entity._optimistic_mode == "heat"  # noqa: SLF001
    entity.async_write_ha_state.assert_called_once()


async def test_set_hvac_mode_unsupported(hass: HomeAssistant) -> None:
    """Test setting unsupported HVAC mode is a no-op."""
    device = _make_mock_device()
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    device.set_mode = AsyncMock(return_value=CommandResult(success=False))
    await entity.async_set_hvac_mode(HVACMode.COOL)
    assert entity._optimistic_mode is None  # noqa: SLF001
    entity.async_write_ha_state.assert_not_called()


async def test_set_hvac_mode_unknown_mode_returns(hass: HomeAssistant) -> None:
    """Test setting an unmapped HVACMode returns without calling device."""
    device = _make_mock_device()
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    with patch.dict(
        "homeassistant.components.mitsubishi_comfort.climate._HVAC_TO_MODE",
        {HVACMode.COOL: Mode.COOL},
        clear=True,
    ):
        await entity.async_set_hvac_mode(HVACMode.HEAT)

    device.set_mode.assert_not_awaited()


async def test_set_temperature_cool_mode(hass: HomeAssistant) -> None:
    """Test setting temperature in cool mode."""
    device = _make_mock_device()
    device.set_cool_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=22.0)
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_temperature(**{ATTR_TEMPERATURE: 22.0})

    device.set_cool_setpoint.assert_awaited_once_with(22.0)
    assert entity._optimistic_cool_setpoint == 22.0  # noqa: SLF001
    entity.async_write_ha_state.assert_called_once()


async def test_set_temperature_heat_mode(hass: HomeAssistant) -> None:
    """Test setting temperature in heat mode."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="heat",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )
    device.set_heat_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=20.0)
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_temperature(**{ATTR_TEMPERATURE: 20.0})

    device.set_heat_setpoint.assert_awaited_once_with(20.0)
    assert entity._optimistic_heat_setpoint == 20.0  # noqa: SLF001


async def test_set_temperature_high_low(hass: HomeAssistant) -> None:
    """Test setting high and low temperatures for auto mode."""
    device = _make_mock_device()
    device.set_cool_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=25.0)
    )
    device.set_heat_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=19.0)
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_temperature(target_temp_high=25.0, target_temp_low=19.0)

    device.set_cool_setpoint.assert_awaited_once_with(25.0)
    device.set_heat_setpoint.assert_awaited_once_with(19.0)
    assert entity._optimistic_cool_setpoint == 25.0  # noqa: SLF001
    assert entity._optimistic_heat_setpoint == 19.0  # noqa: SLF001


async def test_set_temperature_failed_command(hass: HomeAssistant) -> None:
    """Test setting temperature when command fails doesn't set optimistic state."""
    device = _make_mock_device()
    device.set_cool_setpoint = AsyncMock(return_value=CommandResult(success=False))
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_temperature(**{ATTR_TEMPERATURE: 22.0})

    assert entity._optimistic_cool_setpoint is None  # noqa: SLF001
    entity.async_write_ha_state.assert_not_called()


async def test_set_temperature_no_temp(hass: HomeAssistant) -> None:
    """Test set_temperature with no temperature value is a no-op."""
    device = _make_mock_device()
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_temperature()

    device.set_cool_setpoint.assert_not_awaited()
    device.set_heat_setpoint.assert_not_awaited()


async def test_set_fan_mode(hass: HomeAssistant) -> None:
    """Test setting fan mode."""
    device = _make_mock_device()
    device.set_fan_speed = AsyncMock(
        return_value=CommandResult(success=True, value="quiet")
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_fan_mode("quiet")

    device.set_fan_speed.assert_awaited_once_with(FanSpeed.QUIET)
    assert entity._optimistic_fan_speed == "quiet"  # noqa: SLF001
    entity.async_write_ha_state.assert_called_once()


async def test_set_fan_mode_unknown(hass: HomeAssistant) -> None:
    """Test setting an unknown fan mode is a no-op."""
    device = _make_mock_device()
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_fan_mode("turbo")

    device.set_fan_speed.assert_not_awaited()


async def test_set_fan_mode_failed(hass: HomeAssistant) -> None:
    """Test setting fan mode when command fails."""
    device = _make_mock_device()
    device.set_fan_speed = AsyncMock(return_value=CommandResult(success=False))
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_fan_mode("quiet")

    assert entity._optimistic_fan_speed is None  # noqa: SLF001
    entity.async_write_ha_state.assert_not_called()


async def test_set_swing_mode(hass: HomeAssistant) -> None:
    """Test setting swing mode."""
    device = _make_mock_device()
    device.set_vane_direction = AsyncMock(
        return_value=CommandResult(success=True, value="swing")
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_swing_mode("swing")

    device.set_vane_direction.assert_awaited_once_with(VaneDirection.SWING)
    assert entity._optimistic_vane_direction == "swing"  # noqa: SLF001
    entity.async_write_ha_state.assert_called_once()


async def test_set_swing_mode_unknown(hass: HomeAssistant) -> None:
    """Test setting an unknown swing mode is a no-op."""
    device = _make_mock_device()
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_swing_mode("unknown_direction")

    device.set_vane_direction.assert_not_awaited()


async def test_set_swing_mode_failed(hass: HomeAssistant) -> None:
    """Test setting swing mode when command fails."""
    device = _make_mock_device()
    device.set_vane_direction = AsyncMock(return_value=CommandResult(success=False))
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_swing_mode("swing")

    assert entity._optimistic_vane_direction is None  # noqa: SLF001
    entity.async_write_ha_state.assert_not_called()


async def test_turn_off(hass: HomeAssistant) -> None:
    """Test turning off the entity calls set_hvac_mode with OFF."""
    device = _make_mock_device()
    device.set_mode = AsyncMock(return_value=CommandResult(success=True, value="off"))
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_turn_off()

    device.set_mode.assert_awaited_once_with(Mode.OFF)
    assert entity._optimistic_mode == "off"  # noqa: SLF001


# -- Optimistic state tests --


async def test_optimistic_mode_used_for_hvac_mode(hass: HomeAssistant) -> None:
    """Test that optimistic mode overrides device mode."""
    device = _make_mock_device()
    _, entity = _make_coordinator_and_entity(hass, device)

    # Device says cool, but we optimistically set heat
    entity._optimistic_mode = "heat"  # noqa: SLF001
    assert entity.hvac_mode is HVACMode.HEAT


async def test_optimistic_cool_setpoint(hass: HomeAssistant) -> None:
    """Test that optimistic cool setpoint overrides device value."""
    device = _make_mock_device()
    _, entity = _make_coordinator_and_entity(hass, device)

    entity._optimistic_cool_setpoint = 22.0  # noqa: SLF001
    assert entity.target_temperature == 22.0


async def test_optimistic_heat_setpoint(hass: HomeAssistant) -> None:
    """Test that optimistic heat setpoint overrides device value in heat mode."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="heat",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )
    _, entity = _make_coordinator_and_entity(hass, device)

    entity._optimistic_heat_setpoint = 19.0  # noqa: SLF001
    assert entity.target_temperature == 19.0


async def test_optimistic_fan_speed(hass: HomeAssistant) -> None:
    """Test that optimistic fan speed overrides device value."""
    _, entity = _make_coordinator_and_entity(hass)
    entity._optimistic_fan_speed = "quiet"  # noqa: SLF001
    assert entity.fan_mode == "quiet"


async def test_optimistic_vane_direction(hass: HomeAssistant) -> None:
    """Test that optimistic vane direction overrides device value."""
    _, entity = _make_coordinator_and_entity(hass)
    entity._optimistic_vane_direction = "swing"  # noqa: SLF001
    assert entity.swing_mode == "swing"


async def test_coordinator_update_clears_optimistic(hass: HomeAssistant) -> None:
    """Test that coordinator update clears all optimistic state."""
    _, entity = _make_coordinator_and_entity(hass)
    entity.async_write_ha_state = MagicMock()

    entity._optimistic_mode = "heat"  # noqa: SLF001
    entity._optimistic_cool_setpoint = 22.0  # noqa: SLF001
    entity._optimistic_heat_setpoint = 19.0  # noqa: SLF001
    entity._optimistic_fan_speed = "quiet"  # noqa: SLF001
    entity._optimistic_vane_direction = "swing"  # noqa: SLF001

    entity._handle_coordinator_update()  # noqa: SLF001

    assert entity._optimistic_mode is None  # noqa: SLF001
    assert entity._optimistic_cool_setpoint is None  # noqa: SLF001
    assert entity._optimistic_heat_setpoint is None  # noqa: SLF001
    assert entity._optimistic_fan_speed is None  # noqa: SLF001
    assert entity._optimistic_vane_direction is None  # noqa: SLF001
    entity.async_write_ha_state.assert_called_once()


async def test_optimistic_temp_high_low_in_auto(hass: HomeAssistant) -> None:
    """Test optimistic setpoints in auto mode for high/low targets."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="auto",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )
    _, entity = _make_coordinator_and_entity(hass, device)

    entity._optimistic_cool_setpoint = 26.0  # noqa: SLF001
    entity._optimistic_heat_setpoint = 18.0  # noqa: SLF001

    assert entity.target_temperature_high == 26.0
    assert entity.target_temperature_low == 18.0


async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique ID is the device serial."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity.unique_id == "SERIAL001"


async def test_entity_name_is_none(hass: HomeAssistant) -> None:
    """Test entity name is None (uses device name)."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity._attr_name is None  # noqa: SLF001


# -- Entity base class tests --


async def test_entity_available(hass: HomeAssistant) -> None:
    """Test entity availability delegates to coordinator."""
    coordinator, entity = _make_coordinator_and_entity(hass)
    assert entity.available is True

    coordinator._consecutive_failures = 5  # noqa: SLF001
    assert entity.available is False


async def test_entity_device_info(hass: HomeAssistant) -> None:
    """Test device info is populated correctly."""
    _, entity = _make_coordinator_and_entity(hass)
    info = entity.device_info
    assert info["identifiers"] == {("mitsubishi_comfort", "SERIAL001")}
    assert info["name"] == "Living Room"
    assert info["manufacturer"] == "Mitsubishi"


async def test_entity_has_entity_name(hass: HomeAssistant) -> None:
    """Test entity has entity_name attribute set."""
    _, entity = _make_coordinator_and_entity(hass)
    assert entity._attr_has_entity_name is True  # noqa: SLF001


# -- Platform setup test --


async def test_climate_async_setup_entry(hass: HomeAssistant) -> None:
    """Test climate platform setup creates entities for IndoorUnits only."""
    indoor_coordinator = MagicMock()
    indoor_coordinator.device = MagicMock(spec=IndoorUnit)
    indoor_coordinator.device.serial = "SERIAL001"
    indoor_coordinator.device.name = "Living Room"
    indoor_coordinator.device.status = MagicMock()
    indoor_coordinator.device.supported_modes = [Mode.COOL]
    indoor_coordinator.device.supported_fan_speeds = [FanSpeed.AUTO]
    indoor_coordinator.device.supported_vane_directions = []

    kumo_coordinator = MagicMock()
    kumo_coordinator.device = MagicMock()  # Not an IndoorUnit
    # Make isinstance check fail for IndoorUnit
    kumo_coordinator.device.__class__ = type("KumoStation", (), {})

    entry = MagicMock()
    entry.runtime_data = {
        "SERIAL001": indoor_coordinator,
        "SERIAL002": kumo_coordinator,
    }

    added_entities: list = []

    def mock_add_entities(entities: list) -> None:
        added_entities.extend(entities)

    await async_setup_entry(hass, entry, mock_add_entities)

    assert len(added_entities) == 1


async def test_set_temperature_auto_cool_mode(hass: HomeAssistant) -> None:
    """Test setting temperature in autoCool mode sets cool setpoint."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="autoCool",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )
    device.set_cool_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=22.0)
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_temperature(**{ATTR_TEMPERATURE: 22.0})

    device.set_cool_setpoint.assert_awaited_once_with(22.0)
    assert entity._optimistic_cool_setpoint == 22.0  # noqa: SLF001


async def test_set_temperature_auto_heat_mode(hass: HomeAssistant) -> None:
    """Test setting temperature in autoHeat mode sets heat setpoint."""
    device = _make_mock_device()
    device.status = DeviceStatus(
        mode="autoHeat",
        standby=False,
        heat_setpoint=21.0,
        cool_setpoint=24.0,
        room_temperature=23.5,
        fan_speed="auto",
        vane_direction="auto",
        filter_dirty=False,
        defrost=False,
        current_humidity=None,
        outdoor_temperature=None,
        wifi_rssi=None,
        sensor_battery=None,
        sensor_rssi=None,
        run_state="on",
        vane_left_right=None,
        uptime=None,
        firmware_version=None,
        hardware_version=None,
        min_cool_setpoint=18.0,
        max_cool_setpoint=30.0,
        min_heat_setpoint=16.0,
        max_heat_setpoint=28.0,
    )
    device.set_heat_setpoint = AsyncMock(
        return_value=CommandResult(success=True, value=20.0)
    )
    _, entity = _make_coordinator_and_entity(hass, device)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_temperature(**{ATTR_TEMPERATURE: 20.0})

    device.set_heat_setpoint.assert_awaited_once_with(20.0)
    assert entity._optimistic_heat_setpoint == 20.0  # noqa: SLF001
