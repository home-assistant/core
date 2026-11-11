"""Test Tuya climate platform."""

from collections.abc import Callable
import json
from typing import Any
from unittest.mock import call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props
from tuya_sharing import CustomerDevice, Manager
from tuya_sharing.exceptions import ApiRequestException

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_STEP,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.tuya.const import TUYA_HA_SIGNAL_UPDATE_ENTITY
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceNotSupported,
    ServiceValidationError,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from . import TuyaNotificationHelper, initialize_entry


@pytest.fixture(autouse=True)
def platform_autouse():
    """Platform fixture."""
    with patch("homeassistant.components.tuya.PLATFORMS", [Platform.CLIMATE]):
        yield


@pytest.mark.usefixtures("no_quirk")
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_us_customary_system(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    hass.config.units = US_CUSTOMARY_SYSTEM

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    for entity in entity_registry.entities.values():
        state = hass.states.get(entity.entity_id)
        assert state.attributes == snapshot(
            name=entity.entity_id,
            include=props(
                ATTR_CURRENT_TEMPERATURE,
                ATTR_MAX_TEMP,
                ATTR_MIN_TEMP,
                ATTR_TARGET_TEMP_STEP,
                ATTR_TEMPERATURE,
            ),
        )


@pytest.mark.parametrize(
    ("mock_device_code", "entity_id", "service", "service_data", "expected_commands"),
    [
        (
            "kt_5wnlzekkstwcdsvm",
            "climate.air_conditioner",
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 22.7},
            [{"code": "temp_set", "value": 23}],
        ),
        (
            "kt_5wnlzekkstwcdsvm",
            "climate.air_conditioner",
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: 2},
            [{"code": "windspeed", "value": "2"}],
        ),
        (
            "kt_5wnlzekkstwcdsvm",
            "climate.air_conditioner",
            SERVICE_TURN_ON,
            {},
            [{"code": "switch", "value": True}],
        ),
        (
            "kt_5wnlzekkstwcdsvm",
            "climate.air_conditioner",
            SERVICE_TURN_OFF,
            {},
            [{"code": "switch", "value": False}],
        ),
        (
            "kt_ibmmirhhq62mmf1g",
            "climate.master_bedroom_ac",
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.COOL},
            [{"code": "switch", "value": True}, {"code": "mode", "value": "cold"}],
        ),
        (
            "wk_gc1bxoq2hafxpa35",
            "climate.polotentsosushitel",
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "holiday"},
            [{"code": "mode", "value": "holiday"}],
        ),
        (
            "kt_wxqdp6ecfkd78zzz",
            "climate.mini_split",
            SERVICE_SET_SWING_MODE,
            {ATTR_SWING_MODE: "horizontal"},
            [{"code": "switch_horizontal", "value": True}],
        ),
    ],
)
async def test_action(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_id: str,
    service: str,
    service_data: dict[str, Any],
    expected_commands: list[dict[str, Any]],
) -> None:
    """Test climate action."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {
            ATTR_ENTITY_ID: entity_id,
            **service_data,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, expected_commands
    )


@pytest.mark.parametrize(
    ("mock_device_code", "entity_id", "status_updates", "expected_state"),
    [
        pytest.param(
            "wk_cpmgn2cf",
            "climate.bathroom_radiator",
            {"mode": "eco"},
            HVACMode.HEAT_COOL,
            id="preset_without_switch",
        ),
        pytest.param(
            "wk_6kijc7nd",
            "climate.kabinet",
            {"mode": "program", "switch": True},
            HVACMode.HEAT_COOL,
            id="preset_switch_on",
        ),
        pytest.param(
            "wk_6kijc7nd",
            "climate.kabinet",
            {"mode": "program", "switch": False},
            HVACMode.OFF,
            id="preset_switch_off",
        ),
        pytest.param(
            "wk_t94pit6zjbask9qo",
            "climate.floor_thermostat_kitchen",
            {"mode": "off", "switch": True},
            HVACMode.OFF,
            id="hvac_mode_value",
        ),
    ],
)
async def test_hvac_mode_with_preset(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_id: str,
    status_updates: dict[str, Any],
    expected_state: HVACMode,
) -> None:
    """Test the HVAC mode while the mode DP holds a preset."""
    mock_device.status.update(status_updates)
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("mock_device_code", "entity_id", "status_updates", "expected_commands"),
    [
        pytest.param(
            "wk_t94pit6zjbask9qo",
            "climate.floor_thermostat_kitchen",
            {"mode": "off", "switch": True},
            [{"code": "switch", "value": True}, {"code": "mode", "value": "auto"}],
            id="from_hvac_mode_value",
        ),
        pytest.param(
            "wk_t94pit6zjbask9qo",
            "climate.floor_thermostat_kitchen",
            {"mode": "manual", "switch": False},
            [{"code": "switch", "value": True}],
            id="keep_active_preset",
        ),
    ],
)
async def test_set_switch_only_hvac_mode_with_preset(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_id: str,
    status_updates: dict[str, Any],
    expected_commands: list[dict[str, Any]],
) -> None:
    """Test setting the switch-only HVAC mode on a device with presets."""
    mock_device.status.update(status_updates)
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, expected_commands
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["kt_5wnlzekkstwcdsvm"],
)
@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        (
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: 2},
        ),
        (
            SERVICE_SET_HUMIDITY,
            {ATTR_HUMIDITY: 50},
        ),
    ],
)
async def test_action_not_supported(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """Test service action not supported."""
    # Remove windspeed DPCode to simulate a device with no valid fan mode
    mock_device.function.pop("windspeed", None)
    mock_device.status_range.pop("windspeed", None)
    mock_device.status.pop("windspeed", None)

    entity_id = "climate.air_conditioner"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert state.attributes.get(ATTR_FAN_MODE) is None
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {
                ATTR_ENTITY_ID: entity_id,
                **service_data,
            },
            blocking=True,
        )


def _override_temperature_unit(
    device: CustomerDevice, *, temp_set: str, temp_current: str
) -> None:
    """Override the unit of the temp_set/temp_current DPCodes."""
    units = {"temp_set": temp_set, "temp_current": temp_current}
    for container in (device.function, device.status_range):
        for code, unit in units.items():
            if code in container:
                values = json.loads(container[code].values)
                values["unit"] = unit
                container[code].values = json.dumps(values)


@pytest.mark.parametrize("mock_device_code", ["kt_5wnlzekkstwcdsvm"])
@pytest.mark.parametrize(
    (
        "units",
        "temp_current_native_unit",
        "expected_current",
        "temp_set_native_unit",
        "expected_target",
        "service_temperature",
        "expected_set_value",
    ),
    # Note: status in the fixture "temp_set": 23 / "temp_current": 22,
    [
        pytest.param(
            METRIC_SYSTEM, "℉", -5.6, "℉", -5, 25, 77, id="metric-both-fahrenheit"
        ),
        pytest.param(
            METRIC_SYSTEM, "℃", 22.0, "℃", 23.0, 25, 25, id="metric-both-celsius"
        ),
        pytest.param(
            METRIC_SYSTEM,
            "℃",
            22.0,
            "℉",
            -5,
            25,
            77,
            id="metric-set-fahrenheit-current-celsius",
        ),
        pytest.param(
            METRIC_SYSTEM,
            "℉",
            -5.6,
            "℃",
            23.0,
            25,
            25,
            id="metric-set-celsius-current-fahrenheit",
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM, "℉", 22, "℉", 23, 70, 70, id="us-both-fahrenheit"
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM, "℃", 72, "℃", 73, 70, 21, id="us-both-celsius"
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            "℃",
            72,
            "℉",
            23,
            70,
            70,
            id="us-set-fahrenheit-current-celsius",
        ),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            "℉",
            22,
            "℃",
            73,
            70,
            21,
            id="us-set-celsius-current-fahrenheit",
        ),
    ],
)
async def test_temperature_unit_conversion(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    units: UnitSystem,
    temp_current_native_unit: str,
    expected_current: float,
    temp_set_native_unit: str,
    expected_target: float,
    service_temperature: float,
    expected_set_value: int,
) -> None:
    """Test current/target temperature conversion from the device native unit.

    The kt_5wnlzekkstwcdsvm fixture reports its temperatures with the combined
    "℃ ℉" unit, so the definition falls back to the system unit. Overriding the
    DPCode units exercises the conversion between the device native unit and the
    entity unit, independently for temp_set/temp_current and per unit system.
    """
    hass.config.units = units
    _override_temperature_unit(
        mock_device,
        temp_set=temp_set_native_unit,
        temp_current=temp_current_native_unit,
    )

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get("climate.air_conditioner")
    assert state is not None
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == expected_current
    assert state.attributes[ATTR_TEMPERATURE] == expected_target

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.air_conditioner",
            ATTR_TEMPERATURE: service_temperature,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [{"code": "temp_set", "value": expected_set_value}]
    )


IR_AC_ENTITY_ID = "climate.ar"
IR_AC_REPORTED_STATUS = {"power": False, "mode": "0", "temp": 18, "wind": "3"}


def _ir_commands(device_id: str, *commands: tuple[str, Any]) -> list[Any]:
    """Return the expected calls: one command per request."""
    return [
        call(device_id, [{"code": code, "value": value}]) for code, value in commands
    ]


def _ir_restore(
    hvac_mode: HVACMode,
    remote_state: dict[str, int],
    last_on_mode: HVACMode = HVACMode.COOL,
    attributes: dict[str, Any] | None = None,
    **learned: Any,
) -> list[tuple[State, dict[str, Any]]]:
    """Return restore cache data for the infrared air conditioner."""
    return [
        (
            State(IR_AC_ENTITY_ID, hvac_mode, attributes or {}),
            {
                "last_on_mode": last_on_mode,
                "remote_state": remote_state,
                "version": 3,
                **learned,
            },
        )
    ]


def _no_ir_code_error() -> ApiRequestException:
    """Return the error of the cloud when the IR library has no code."""
    return ApiRequestException(
        error_code="2050", error_message="no infrared code for this command"
    )


def _reject_commands(*rejected: tuple[str, Any]) -> Callable[[str, list], None]:
    """Return a send_commands side effect rejecting some commands."""

    def _send_commands(device_id: str, commands: list[dict[str, Any]]) -> None:
        for command in commands:
            if (command["code"], command["value"]) in rejected:
                raise _no_ir_code_error()

    return _send_commands


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_initial_state(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test the assumed state of an infrared air conditioner after setup."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes["assumed_state"] is True
    assert state.attributes["hvac_modes"] == [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.AUTO,
        HVACMode.FAN_ONLY,
        HVACMode.DRY,
    ]
    assert state.attributes["fan_modes"] == ["auto", "low", "medium", "high"]
    assert state.attributes[ATTR_FAN_MODE] == "auto"
    assert state.attributes[ATTR_MIN_TEMP] == 16
    assert state.attributes[ATTR_MAX_TEMP] == 30
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == 1
    assert state.attributes[ATTR_TEMPERATURE] == 24


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_unknown_remote_state(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test all settings are sent once while the remote state is unknown."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    # Any command powers the unit on: no separate PowerOn.
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("M", 1), ("F", 0), ("T", 24)
    )
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.HEAT

    # The remote state is now known: only the change is sent.
    mock_manager.send_commands.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("M", 0)
    )
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.COOL


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_turn_off_and_on(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test turning off, then on again with a single PowerOn."""
    mock_restore_cache_with_extra_data(
        hass, _ir_restore(HVACMode.HEAT, {"M": 1, "T": 24, "F": 0}, HVACMode.HEAT)
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.HEAT

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("PowerOff", "PowerOff")
    )
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.OFF

    mock_manager.send_commands.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("PowerOn", "PowerOn")
    )
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.HEAT


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_settings_while_off(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test settings changed while off are sent with the power on."""
    mock_restore_cache_with_extra_data(
        hass, _ir_restore(HVACMode.OFF, {"M": 0, "T": 24, "F": 0})
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_TEMPERATURE: 21},
        blocking=True,
    )
    mock_manager.send_commands.assert_not_called()
    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 21

    # The temperature command powers the unit on: one command only.
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("T", 21)
    )
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.COOL

    # Fan changed while off.
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_FAN_MODE: "high"},
        blocking=True,
    )
    assert hass.states.get(IR_AC_ENTITY_ID).attributes[ATTR_FAN_MODE] == "high"
    mock_manager.send_commands.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("F", 3)
    )


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
@pytest.mark.parametrize(
    ("service", "service_data", "expected_commands"),
    [
        pytest.param(
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 22},
            [("T", 22)],
            id="temperature",
        ),
        pytest.param(
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 24},
            [],
            id="same_temperature",
        ),
        pytest.param(
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: "medium"},
            [("F", 2)],
            id="fan_mode",
        ),
        pytest.param(
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            [("M", 1)],
            id="hvac_mode",
        ),
        pytest.param(
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 26, ATTR_HVAC_MODE: HVACMode.HEAT},
            [("M", 1), ("T", 26)],
            id="temperature_and_mode",
        ),
        pytest.param(
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 26, ATTR_HVAC_MODE: HVACMode.OFF},
            [("PowerOff", "PowerOff")],
            id="temperature_and_off",
        ),
        pytest.param(
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.OFF},
            [("PowerOff", "PowerOff")],
            id="off",
        ),
        pytest.param(
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.AUTO},
            [("T", 25), ("M", 2)],
            id="auto_locks_temperature",
        ),
        pytest.param(
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.DRY},
            [("T", 25), ("F", 1), ("M", 4)],
            id="dry_needs_low_fan",
        ),
    ],
)
async def test_infrared_ac_settings_while_on(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service: str,
    service_data: dict[str, Any],
    expected_commands: list[tuple[str, Any]],
) -> None:
    """Test only the changed settings are sent while the unit is on."""
    mock_restore_cache_with_extra_data(
        hass,
        _ir_restore(
            HVACMode.COOL,
            {"M": 0, "T": 24, "F": 0},
            attributes={ATTR_TEMPERATURE: 24, ATTR_FAN_MODE: "auto"},
        ),
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.COOL

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, **service_data},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, *expected_commands
    )


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_locked_modes(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test the temperature and fan speeds in auto, fan only and dry."""
    mock_restore_cache_with_extra_data(
        hass,
        _ir_restore(
            HVACMode.COOL,
            {"M": 0, "T": 22, "F": 2},
            attributes={ATTR_TEMPERATURE: 22, ATTR_FAN_MODE: "medium"},
        ),
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Cool 22 with a medium fan to fan only: 25 °C and auto fan first.
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("T", 25), ("F", 0), ("M", 3)
    )
    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.FAN_ONLY
    assert state.attributes["fan_modes"] == ["auto"]
    assert state.attributes[ATTR_FAN_MODE] == "auto"
    assert ATTR_TEMPERATURE not in state.attributes
    assert not (
        state.attributes["supported_features"] & ClimateEntityFeature.TARGET_TEMPERATURE
    )
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_TEMPERATURE: 20},
            blocking=True,
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_FAN_MODE: "high"},
            blocking=True,
        )

    # Fan only (auto fan only) to dry (low fan only): through cool.
    mock_manager.send_commands.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.DRY},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("M", 0), ("F", 1), ("M", 4)
    )
    assert hass.states.get(IR_AC_ENTITY_ID).attributes["fan_modes"] == ["low"]

    # Back to cool: the temperature stays at 25 like in the Tuya app.
    mock_manager.send_commands.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )
    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_TEMPERATURE] == 25
    assert state.attributes["fan_modes"] == ["auto", "low", "medium", "high"]


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_mode_through_cool(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test reaching dry from auto, where no fan change is possible."""
    mock_restore_cache_with_extra_data(
        hass,
        _ir_restore(HVACMode.AUTO, {"M": 2, "T": 25, "F": 0}, HVACMode.AUTO),
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.DRY},
        blocking=True,
    )
    # Low fan is not offered in auto: go through cool.
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("M", 0), ("F", 1), ("M", 4)
    )
    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.DRY
    assert state.attributes[ATTR_FAN_MODE] == "low"
    assert state.attributes["fan_modes"] == ["low"]


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_mode_rejected(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test a rejected mode is reported and stays offered."""
    mock_restore_cache_with_extra_data(
        hass,
        _ir_restore(
            HVACMode.COOL,
            {"M": 0, "T": 24, "F": 3},
            attributes={ATTR_TEMPERATURE: 24, ATTR_FAN_MODE: "high"},
        ),
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    mock_manager.send_commands.side_effect = _reject_commands(("M", 1))

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        )
    assert exc_info.value.translation_key == "infrared_ac_mode_not_supported"
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("M", 1)
    )
    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.COOL
    assert HVACMode.HEAT in state.attributes["hvac_modes"]


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_fan_mode_rejected(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test a rejected fan speed is reported and stays offered."""
    mock_restore_cache_with_extra_data(
        hass,
        _ir_restore(
            HVACMode.HEAT,
            {"M": 1, "T": 24, "F": 0},
            HVACMode.HEAT,
            attributes={ATTR_TEMPERATURE: 24, ATTR_FAN_MODE: "auto"},
        ),
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    mock_manager.send_commands.side_effect = _reject_commands(("F", 3))

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_FAN_MODE: "high"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "infrared_ac_fan_mode_not_supported"
    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.attributes[ATTR_FAN_MODE] == "auto"
    assert state.attributes["fan_modes"] == ["auto", "low", "medium", "high"]


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_set_temperature_and_mode_from_off(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test setting temperature with a mode from off sends one command."""
    mock_restore_cache_with_extra_data(
        hass, _ir_restore(HVACMode.OFF, {"M": 0, "T": 24, "F": 0})
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: IR_AC_ENTITY_ID,
            ATTR_TEMPERATURE: 19,
            ATTR_HVAC_MODE: HVACMode.COOL,
        },
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("T", 19)
    )
    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_TEMPERATURE] == 19


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_restore_state(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test the assumed state, last used mode and remote state are restored."""
    mock_restore_cache_with_extra_data(
        hass,
        _ir_restore(
            HVACMode.OFF,
            {"M": 1, "T": 27, "F": 1},
            HVACMode.HEAT,
            {ATTR_TEMPERATURE: 27, ATTR_FAN_MODE: "low"},
        ),
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 27
    assert state.attributes[ATTR_FAN_MODE] == "low"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("PowerOn", "PowerOn")
    )
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.HEAT


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_restore_state_without_extra_data(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test the last used mode falls back to the restored state."""
    mock_restore_cache(hass, [State(IR_AC_ENTITY_ID, HVACMode.HEAT)])
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.HEAT

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    mock_manager.send_commands.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("M", 1), ("F", 0), ("T", 24)
    )


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_restore_seen(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test combinations the remote was seen in are kept across restarts."""
    mock_restore_cache_with_extra_data(
        hass,
        _ir_restore(
            HVACMode.OFF,
            {"M": 0, "T": 24, "F": 0},
            HVACMode.DRY,
            seen_fan_modes={HVACMode.DRY: ["medium", "bogus"], "bogus": []},
            fixed_temperatures={HVACMode.DRY: 26, HVACMode.COOL: 20},
        ),
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(IR_AC_ENTITY_ID)
    assert len(state.attributes["hvac_modes"]) == 6
    # Dry is the last used mode: its fan speeds are shown while off.
    assert state.attributes["fan_modes"] == ["low", "medium"]

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("T", 26), ("F", 1), ("M", 4)
    )


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_ignores_old_stored_data(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test data stored by an older version is ignored, except the state."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(IR_AC_ENTITY_ID, HVACMode.OFF),
                {
                    "last_on_mode": HVACMode.DRY,
                    "remote_state": {"M": 0, "T": 24, "F": 0},
                    "seen_fan_modes": {HVACMode.DRY: ["high"]},
                    "learned_version": 2,
                },
            )
        ],
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    assert hass.states.get(IR_AC_ENTITY_ID).attributes["fan_modes"] == ["low"]
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("T", 25), ("F", 1), ("M", 4)
    )


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_reported_remote_state(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the remote state reported by the cloud is used and followed."""
    mock_device.status.update(IR_AC_REPORTED_STATUS)
    # The reported state wins over the restored one.
    mock_restore_cache_with_extra_data(
        hass,
        _ir_restore(HVACMode.HEAT, {"M": 1, "T": 30, "F": 0}),
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 18
    assert state.attributes[ATTR_FAN_MODE] == "high"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("PowerOn", "PowerOn")
    )
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.COOL
    # Reports lagging behind the command have had time to arrive. None did:
    # the reported state is older than the command and is not shown.
    freezer.tick(11)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.COOL

    # Changed elsewhere (for example in the Tuya app).
    await notification_helper.async_send_device_update(
        mock_device, {"power": True, "mode": "1", "temp": 26, "wind": "1"}
    )
    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 26
    assert state.attributes[ATTR_FAN_MODE] == "low"

    # Dry with a medium fan used in the Tuya app: the fan speed is offered
    # and the locked temperature is learned.
    await notification_helper.async_send_device_update(
        mock_device, {"mode": "4", "temp": 24, "wind": "2"}
    )
    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.DRY
    assert state.attributes["fan_modes"] == ["low", "medium"]
    assert state.attributes[ATTR_FAN_MODE] == "medium"

    await notification_helper.async_send_device_update(mock_device, {"power": False})
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.OFF

    # Powering on again resumes dry with one command.
    mock_manager.send_commands.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("PowerOn", "PowerOn")
    )
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.DRY


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_intermediate_reports(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test reports of intermediate states are not shown."""
    mock_device.status.update({"power": True, "mode": "4", "temp": 25, "wind": "1"})
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.DRY

    def _report_each_command(device_id: str, commands: list) -> None:
        """Report the state after each command, like the cloud does."""
        command = commands[0]
        status = {"M": "mode", "F": "wind", "T": "temp"}[command["code"]]
        value = command["value"] if status == "temp" else str(command["value"])
        mock_device.status[status] = value
        for listener in mock_manager.device_listeners:
            hass.loop.call_soon_threadsafe(
                listener.update_device, mock_device, [status], None
            )

    mock_manager.send_commands.side_effect = _report_each_command
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
        blocking=True,
    )
    await hass.async_block_till_done()
    # Through cool, but cool was never shown.
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("M", 0), ("F", 0), ("M", 3)
    )
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.FAN_ONLY

    # A late report of an intermediate state is not shown either.
    await notification_helper.async_send_device_update(
        mock_device, {"mode": "0", "wind": "0"}
    )
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.FAN_ONLY

    # Once reports had time to catch up, the reported state is shown.
    freezer.tick(11)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.COOL


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_actions_do_not_interleave(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test a turn off waits for the commands of a mode change to finish."""
    mock_restore_cache_with_extra_data(
        hass, _ir_restore(HVACMode.COOL, {"M": 0, "T": 24, "F": 2})
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    def _turn_off_while_sending(device_id: str, commands: list[dict[str, Any]]) -> None:
        """Turn off while the first command of the mode change is sent."""
        if commands[0]["code"] == "T":
            hass.async_create_task(
                hass.services.async_call(
                    CLIMATE_DOMAIN,
                    SERVICE_TURN_OFF,
                    {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
                    blocking=True,
                ),
                eager_start=True,
            )

    mock_manager.send_commands.side_effect = _turn_off_while_sending
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.DRY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("T", 25), ("F", 1), ("M", 4), ("PowerOff", "PowerOff")
    )
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.OFF


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_restore_target_temperature(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test the stored target temperature wins over the state attribute."""
    mock_restore_cache_with_extra_data(
        hass,
        _ir_restore(
            HVACMode.OFF,
            {"M": 0, "T": 22, "F": 0},
            attributes={ATTR_TEMPERATURE: 30},
            target_temperature=22.0,
        ),
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    assert hass.states.get(IR_AC_ENTITY_ID).attributes[ATTR_TEMPERATURE] == 22


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_restore_temperature_attribute_in_fahrenheit(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test a restored temperature attribute is converted to Celsius."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_restore_cache(
        hass, [State(IR_AC_ENTITY_ID, HVACMode.OFF, {ATTR_TEMPERATURE: 75})]
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("M", 1), ("F", 0), ("T", 24)
    )


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_between_locked_temperatures(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test changing between modes locked at different temperatures."""
    mock_restore_cache_with_extra_data(
        hass,
        _ir_restore(
            HVACMode.DRY,
            {"M": 4, "T": 24, "F": 1},
            HVACMode.DRY,
            fixed_temperatures={HVACMode.DRY: 24},
        ),
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
        blocking=True,
    )
    # Dry only has codes at 24 °C: the temperature changes in cool.
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("M", 0), ("T", 25), ("F", 0), ("M", 3)
    )
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.FAN_ONLY


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_unknown_remote_state_rejected(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test a rejection from an unknown remote state is retried through cool."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    sent: list[tuple[str, Any]] = []

    def _send_commands(device_id: str, commands: list[dict[str, Any]]) -> None:
        """Reject fan only unless the fan was set to auto (hub left in dry)."""
        command = (commands[0]["code"], commands[0]["value"])
        if command == ("M", 3) and ("F", 0) not in sent:
            raise _no_ir_code_error()
        sent.append(command)

    mock_manager.send_commands.side_effect = _send_commands
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("T", 25), ("M", 3), ("M", 0), ("F", 0), ("M", 3)
    )
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.FAN_ONLY


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_partial_change_shown(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test the state accepted commands left the unit in is shown on failure."""
    mock_restore_cache_with_extra_data(
        hass,
        _ir_restore(
            HVACMode.OFF,
            {"M": 0, "T": 24, "F": 2},
            attributes={ATTR_TEMPERATURE: 24, ATTR_FAN_MODE: "medium"},
        ),
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    mock_manager.send_commands.side_effect = _reject_commands(("M", 4))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.DRY},
            blocking=True,
        )
    # The accepted temperature and fan commands powered the unit on in cool.
    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_TEMPERATURE] == 25
    assert state.attributes[ATTR_FAN_MODE] == "low"


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_temperature_rounded_to_step(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test the sent and shown temperature are rounded to the step."""
    mock_restore_cache_with_extra_data(
        hass, _ir_restore(HVACMode.COOL, {"M": 0, "T": 24, "F": 0})
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_TEMPERATURE: 22.6},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("T", 23)
    )
    assert hass.states.get(IR_AC_ENTITY_ID).attributes[ATTR_TEMPERATURE] == 23


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_previous_settle_check_skipped(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the settle check of an action does not run during the next one."""
    mock_device.status.update({"power": True, "mode": "4", "temp": 25, "wind": "1"})
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    freezer.tick(9)
    shown: list[str] = []
    async_track_state_change_event(
        hass, IR_AC_ENTITY_ID, lambda event: shown.append(event.data["new_state"].state)
    )

    def _report_and_settle_while_sending(
        device_id: str, commands: list[dict[str, Any]]
    ) -> None:
        """Report cool and pass the previous settle time while in cool."""
        if commands[0] == {"code": "M", "value": 0}:
            mock_device.status.update({"power": True, "mode": "0"})
            async_dispatcher_send(
                hass,
                f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{mock_device.id}",
                ["power", "mode"],
                None,
            )
            freezer.tick(2)
            async_fire_time_changed(hass)

    mock_manager.send_commands.side_effect = _report_and_settle_while_sending
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list[-3:] == _ir_commands(
        mock_device.id, ("M", 0), ("F", 0), ("M", 3)
    )
    assert HVACMode.COOL not in shown
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.FAN_ONLY


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_first_report_after_command(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a first report arriving while commands settle is shown later."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    # The first report arrives while the commands settle, with another state.
    report = {"power": True, "mode": "0", "temp": 24, "wind": "0"}
    mock_device.status.update(report)
    await notification_helper.async_send_device_update(mock_device, report)
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.HEAT

    freezer.tick(11)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.COOL


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_rejected_temperature_shown(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test an accepted mode is shown when the following temperature fails."""
    mock_restore_cache_with_extra_data(
        hass, _ir_restore(HVACMode.OFF, {"M": 0, "T": 24, "F": 0})
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    mock_manager.send_commands.side_effect = _reject_commands(("T", 19))

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: IR_AC_ENTITY_ID,
                ATTR_TEMPERATURE: 19,
                ATTR_HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )
    # The accepted mode command powered the unit on in heat.
    assert mock_manager.send_commands.call_args_list == _ir_commands(
        mock_device.id, ("M", 1), ("T", 19)
    )
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.HEAT


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_other_errors_not_bridged(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test only a missing IR code is retried through cool."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    mock_manager.send_commands.side_effect = ApiRequestException(
        error_code="1109", error_message="param is wrong"
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
            blocking=True,
        )
    # No retry through cool, and no misleading "not supported" error.
    assert exc_info.value.translation_key == "command_rejected"
    assert mock_manager.send_commands.call_count == 1
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.OFF


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_turn_on_uses_mode_set_meanwhile(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test a turn on queued behind a mode change turns on in the new mode."""
    mock_restore_cache_with_extra_data(
        hass, _ir_restore(HVACMode.COOL, {"M": 0, "T": 24, "F": 2})
    )
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    queued = False

    def _turn_on_while_sending(device_id: str, commands: list[dict[str, Any]]) -> None:
        """Turn on while the first command of the mode change is sent."""
        nonlocal queued
        if not queued:
            queued = True
            hass.async_create_task(
                hass.services.async_call(
                    CLIMATE_DOMAIN,
                    SERVICE_TURN_ON,
                    {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
                    blocking=True,
                ),
                eager_start=True,
            )

    mock_manager.send_commands.side_effect = _turn_on_while_sending
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    await hass.async_block_till_done()
    # The queued turn on did not switch back to the mode used before.
    assert ("M", 0) not in [
        (command["code"], command["value"])
        for call in mock_manager.send_commands.call_args_list
        for command in call.args[1]
    ]
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.HEAT


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_only_fresh_status_fields_applied(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a report of one field does not bring back the old other fields."""
    mock_device.status.update({"power": False, "mode": "0", "temp": 24, "wind": "2"})
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: IR_AC_ENTITY_ID,
            ATTR_TEMPERATURE: 19,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )
    # Only the temperature is reported: power and mode are still the old ones.
    mock_device.status.update({"temp": 19})
    await notification_helper.async_send_device_update(mock_device, {"temp": 19})

    freezer.tick(11)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 19


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_late_report_of_one_field(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a report of one field after the settle time keeps the other fields."""
    mock_device.status.update({"power": False, "mode": "0", "temp": 24, "wind": "2"})
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: IR_AC_ENTITY_ID,
            ATTR_TEMPERATURE: 19,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )
    freezer.tick(11)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(IR_AC_ENTITY_ID).state == HVACMode.HEAT

    # The cached power and mode are older than the commands.
    mock_device.status.update({"temp": 21})
    await notification_helper.async_send_device_update(mock_device, {"temp": 21})
    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 21


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_command_rejected(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test other rejected commands are only reported."""
    mock_device.status.update(IR_AC_REPORTED_STATUS)
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    mock_manager.send_commands.side_effect = _no_ir_code_error()

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
            blocking=True,
        )
    assert exc_info.value.translation_key == "command_rejected"
    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.OFF
    assert len(state.attributes["hvac_modes"]) == 6


@pytest.mark.parametrize("mock_device_code", ["infrared_ac_47peys"])
async def test_infrared_ac_not_supported(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test no entity is created without the mode command."""
    mock_device.function.pop("M")
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    assert hass.states.get(IR_AC_ENTITY_ID) is None
