"""Test Tuya climate platform."""

import json
from typing import Any
from unittest.mock import call, patch

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    mock_restore_cache,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
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
    ClimateService,
    ClimateServiceArgument,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform, TargetKey
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceNotSupported
from homeassistant.helpers import entity_registry as er
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
        ClimateService.SET_HVAC_MODE,
        {
            TargetKey.ENTITY_ID: entity_id,
            ClimateServiceArgument.HVAC_MODE: HVACMode.HEAT_COOL,
        },
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
        ClimateService.SET_TEMPERATURE,
        {
            TargetKey.ENTITY_ID: "climate.air_conditioner",
            ClimateServiceArgument.TEMPERATURE: service_temperature,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [{"code": "temp_set", "value": expected_set_value}]
    )


IR_AC_DEVICE_CODE = "infrared_ac_1ownck"
IR_AC_ENTITY_ID = "climate.infrared_ac"


@pytest.mark.parametrize("mock_device_code", [IR_AC_DEVICE_CODE])
async def test_infrared_ac_state(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test the assumed state of an IR air conditioner."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.HEAT_COOL,
        HVACMode.FAN_ONLY,
        HVACMode.DRY,
    ]
    assert state.attributes[ATTR_FAN_MODES] == ["auto", "low", "medium", "high"]
    assert state.attributes[ATTR_FAN_MODE] == "auto"
    assert state.attributes[ATTR_MIN_TEMP] == 16
    assert state.attributes[ATTR_MAX_TEMP] == 30
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == 1
    assert state.attributes[ATTR_TEMPERATURE] == 23
    # The device does not report any status, so nothing is sent on setup
    assert mock_manager.send_commands.call_count == 0


@pytest.mark.parametrize(
    ("service", "service_data", "expected_commands"),
    [
        (
            SERVICE_TURN_ON,
            {},
            [
                {"code": "PowerOn", "value": "PowerOn"},
                {"code": "M", "value": 0},
                {"code": "T", "value": 23},
                {"code": "F", "value": 0},
            ],
        ),
        (
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            [
                {"code": "PowerOn", "value": "PowerOn"},
                {"code": "M", "value": 1},
                {"code": "T", "value": 23},
                {"code": "F", "value": 0},
            ],
        ),
        (
            SERVICE_TURN_OFF,
            {},
            [{"code": "PowerOff", "value": "PowerOff"}],
        ),
    ],
)
@pytest.mark.parametrize("mock_device_code", [IR_AC_DEVICE_CODE])
async def test_infrared_ac_action(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service: str,
    service_data: dict[str, Any],
    expected_commands: list[dict[str, Any]],
) -> None:
    """Test IR air conditioner actions.

    Every command is sent in its own request, as the device API rejects
    multiple commands for IR devices.
    """
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, **service_data},
        blocking=True,
    )

    assert mock_manager.send_commands.call_args_list == [
        call(mock_device.id, [command]) for command in expected_commands
    ]


@pytest.mark.parametrize(
    ("service", "service_data", "expected_command"),
    [
        (SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 26}, {"code": "T", "value": 26}),
        # Values between two steps are rounded
        (SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 26.7}, {"code": "T", "value": 27}),
        (SERVICE_SET_FAN_MODE, {ATTR_FAN_MODE: "high"}, {"code": "F", "value": 3}),
    ],
)
@pytest.mark.parametrize("mock_device_code", [IR_AC_DEVICE_CODE])
async def test_infrared_ac_action_when_on(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    service: str,
    service_data: dict[str, Any],
    expected_command: dict[str, Any],
) -> None:
    """Test IR air conditioner actions while the device is on."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    mock_manager.send_commands.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, **service_data},
        blocking=True,
    )

    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [expected_command]
    )


@pytest.mark.parametrize("mock_device_code", [IR_AC_DEVICE_CODE])
async def test_infrared_ac_changes_when_off(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test that changes while off are only tracked locally."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_TEMPERATURE: 27},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID, ATTR_FAN_MODE: "high"},
        blocking=True,
    )

    assert mock_manager.send_commands.call_count == 0
    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 27
    assert state.attributes[ATTR_FAN_MODE] == "high"

    # The remembered values are sent when the device is turned on
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    assert mock_manager.send_commands.call_args_list == [
        call(mock_device.id, [{"code": "PowerOn", "value": "PowerOn"}]),
        call(mock_device.id, [{"code": "M", "value": 0}]),
        call(mock_device.id, [{"code": "T", "value": 27}]),
        call(mock_device.id, [{"code": "F", "value": 3}]),
    ]


@pytest.mark.parametrize("mock_device_code", [IR_AC_DEVICE_CODE])
async def test_infrared_ac_restore_state(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test that the locally tracked state is restored after a restart."""
    mock_restore_cache(
        hass,
        [
            State(
                IR_AC_ENTITY_ID,
                HVACMode.HEAT,
                {
                    ATTR_TEMPERATURE: 25,
                    ATTR_FAN_MODE: "high",
                },
            )
        ],
    )

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 25
    assert state.attributes[ATTR_FAN_MODE] == "high"

    # Turning off and on again restores the restored HVAC mode
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
    assert mock_manager.send_commands.call_args_list == [
        call(mock_device.id, [{"code": "PowerOn", "value": "PowerOn"}]),
        call(mock_device.id, [{"code": "M", "value": 1}]),
        call(mock_device.id, [{"code": "T", "value": 25}]),
        call(mock_device.id, [{"code": "F", "value": 3}]),
    ]


@pytest.mark.parametrize("mock_device_code", [IR_AC_DEVICE_CODE])
async def test_infrared_ac_push_update(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
) -> None:
    """Test that push updates from the hub update the entity state."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Simulate the hub reporting an active AC state
    mock_device.status = {"power": True, "mode": 1, "temp": 25, "wind": 2}
    await notification_helper.async_send_device_update(
        mock_device,
        {"power": True, "mode": 1, "temp": 25, "wind": 2},
    )

    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 25
    assert state.attributes[ATTR_FAN_MODE] == "medium"


@pytest.mark.parametrize("mock_device_code", [IR_AC_DEVICE_CODE])
async def test_infrared_ac_push_update_power_off(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
) -> None:
    """Test that a push update with power off sets the entity to off."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Turn on first
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    mock_manager.send_commands.reset_mock()

    # Simulate hub reporting power off
    mock_device.status = {"power": False, "mode": 0, "temp": 23, "wind": 0}
    await notification_helper.async_send_device_update(
        mock_device,
        {"power": False},
    )

    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF


@pytest.mark.parametrize("mock_device_code", [IR_AC_DEVICE_CODE])
async def test_infrared_ac_push_update_partial(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
) -> None:
    """Test that partial push updates only update the reported fields."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Turn on first
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: IR_AC_ENTITY_ID},
        blocking=True,
    )
    mock_manager.send_commands.reset_mock()

    # Simulate hub reporting only a temperature change
    mock_device.status = {"power": True, "mode": 0, "temp": 28, "wind": 0}
    await notification_helper.async_send_device_update(
        mock_device,
        {"temp": 28},
    )

    state = hass.states.get(IR_AC_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_TEMPERATURE] == 28
    assert state.attributes[ATTR_FAN_MODE] == "auto"
