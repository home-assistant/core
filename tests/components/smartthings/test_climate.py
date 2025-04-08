"""Test for the SmartThings climate platform."""

from typing import Any
from unittest.mock import AsyncMock, call

from pysmartthings import Attribute, Capability, Command, Status
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_HORIZONTAL,
    SWING_OFF,
    HVACAction,
    HVACMode,
)
from homeassistant.components.smartthings.const import MAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    set_attribute_value,
    setup_integration,
    snapshot_smartthings_entities,
    trigger_update,
)

from tests.common import MockConfigEntry


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.CLIMATE)


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_ac_set_fan_mode(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate set fan mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.ac_office_granit", ATTR_FAN_MODE: "auto"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        Capability.AIR_CONDITIONER_FAN_MODE,
        Command.SET_FAN_MODE,
        MAIN,
        argument="auto",
    )


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_ac_set_hvac_mode_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting AC HVAC mode to off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.ac_office_granit", ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        Capability.SWITCH,
        Command.OFF,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
@pytest.mark.parametrize(
    ("hvac_mode", "argument"),
    [
        (HVACMode.HEAT_COOL, "auto"),
        (HVACMode.COOL, "cool"),
        (HVACMode.DRY, "dry"),
        (HVACMode.HEAT, "heat"),
        (HVACMode.FAN_ONLY, "fanOnly"),
    ],
)
async def test_ac_set_hvac_mode(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    hvac_mode: HVACMode,
    argument: str,
) -> None:
    """Test setting AC HVAC mode."""
    set_attribute_value(
        devices,
        Capability.AIR_CONDITIONER_MODE,
        Attribute.SUPPORTED_AC_MODES,
        ["auto", "cool", "dry", "heat", "fanOnly"],
    )
    set_attribute_value(devices, Capability.SWITCH, Attribute.SWITCH, "on")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.ac_office_granit", ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        Capability.AIR_CONDITIONER_MODE,
        Command.SET_AIR_CONDITIONER_MODE,
        MAIN,
        argument=argument,
    )


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_ac_set_hvac_mode_turns_on(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting AC HVAC mode turns on the device if it is off."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.ac_office_granit",
            ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
        },
        blocking=True,
    )
    assert devices.execute_device_command.mock_calls == [
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.SWITCH,
            Command.ON,
            MAIN,
        ),
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.AIR_CONDITIONER_MODE,
            Command.SET_AIR_CONDITIONER_MODE,
            MAIN,
            argument="auto",
        ),
    ]


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_ac_set_hvac_mode_wind(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting AC HVAC mode to wind if the device supports it."""
    set_attribute_value(
        devices,
        Capability.AIR_CONDITIONER_MODE,
        Attribute.SUPPORTED_AC_MODES,
        ["auto", "cool", "dry", "heat", "wind"],
    )
    set_attribute_value(devices, Capability.SWITCH, Attribute.SWITCH, "on")

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.ac_office_granit", ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        Capability.AIR_CONDITIONER_MODE,
        Command.SET_AIR_CONDITIONER_MODE,
        MAIN,
        argument="wind",
    )


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_ac_set_temperature(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting AC temperature."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.ac_office_granit", ATTR_TEMPERATURE: 23},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        Capability.THERMOSTAT_COOLING_SETPOINT,
        Command.SET_COOLING_SETPOINT,
        MAIN,
        argument=23,
    )


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_ac_set_temperature_and_hvac_mode_while_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting AC temperature and HVAC mode while off."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.ac_office_granit",
            ATTR_TEMPERATURE: 23,
            ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
        },
        blocking=True,
    )
    assert devices.execute_device_command.mock_calls == [
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.SWITCH,
            Command.ON,
            MAIN,
        ),
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.THERMOSTAT_COOLING_SETPOINT,
            Command.SET_COOLING_SETPOINT,
            MAIN,
            argument=23.0,
        ),
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.SWITCH,
            Command.ON,
            MAIN,
        ),
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.AIR_CONDITIONER_MODE,
            Command.SET_AIR_CONDITIONER_MODE,
            MAIN,
            argument="auto",
        ),
    ]


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_ac_set_temperature_and_hvac_mode(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting AC temperature and HVAC mode."""
    set_attribute_value(devices, Capability.SWITCH, Attribute.SWITCH, "on")
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.ac_office_granit",
            ATTR_TEMPERATURE: 23,
            ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
        },
        blocking=True,
    )
    assert devices.execute_device_command.mock_calls == [
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.THERMOSTAT_COOLING_SETPOINT,
            Command.SET_COOLING_SETPOINT,
            MAIN,
            argument=23.0,
        ),
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.AIR_CONDITIONER_MODE,
            Command.SET_AIR_CONDITIONER_MODE,
            MAIN,
            argument="auto",
        ),
    ]


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_ac_set_temperature_and_hvac_mode_off(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting AC temperature and HVAC mode OFF."""
    set_attribute_value(devices, Capability.SWITCH, Attribute.SWITCH, "on")
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.ac_office_granit",
            ATTR_TEMPERATURE: 23,
            ATTR_HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )
    assert devices.execute_device_command.mock_calls == [
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.SWITCH,
            Command.OFF,
            MAIN,
        ),
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.THERMOSTAT_COOLING_SETPOINT,
            Command.SET_COOLING_SETPOINT,
            MAIN,
            argument=23.0,
        ),
    ]


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
@pytest.mark.parametrize(
    ("service", "command"),
    [
        (SERVICE_TURN_ON, Command.ON),
        (SERVICE_TURN_OFF, Command.OFF),
    ],
)
async def test_ac_toggle_power(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    command: Command,
) -> None:
    """Test toggling AC power."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "climate.ac_office_granit"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        Capability.SWITCH,
        command,
        MAIN,
    )


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_ac_set_swing_mode(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate set swing mode."""
    set_attribute_value(
        devices,
        Capability.FAN_OSCILLATION_MODE,
        Attribute.SUPPORTED_FAN_OSCILLATION_MODES,
        ["fixed"],
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: "climate.ac_office_granit", ATTR_SWING_MODE: SWING_OFF},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        Capability.FAN_OSCILLATION_MODE,
        Command.SET_FAN_OSCILLATION_MODE,
        MAIN,
        argument="fixed",
    )


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_ac_set_preset_mode(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test climate set preset mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.ac_office_granit", ATTR_PRESET_MODE: "windFree"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        Capability.CUSTOM_AIR_CONDITIONER_OPTIONAL_MODE,
        Command.SET_AC_OPTIONAL_MODE,
        MAIN,
        argument="windFree",
    )


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_ac_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("climate.ac_office_granit").state == HVACMode.OFF

    await trigger_update(
        hass,
        devices,
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        Capability.SWITCH,
        Attribute.SWITCH,
        "on",
    )

    assert hass.states.get("climate.ac_office_granit").state == HVACMode.HEAT


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
@pytest.mark.parametrize(
    (
        "capability",
        "attribute",
        "value",
        "state_attribute",
        "original_value",
        "expected_value",
    ),
    [
        (
            Capability.TEMPERATURE_MEASUREMENT,
            Attribute.TEMPERATURE,
            20,
            ATTR_CURRENT_TEMPERATURE,
            25,
            20,
        ),
        (
            Capability.AIR_CONDITIONER_FAN_MODE,
            Attribute.FAN_MODE,
            "auto",
            ATTR_FAN_MODE,
            "low",
            "auto",
        ),
        (
            Capability.AIR_CONDITIONER_FAN_MODE,
            Attribute.SUPPORTED_AC_FAN_MODES,
            ["low", "auto"],
            ATTR_FAN_MODES,
            ["auto", "low", "medium", "high", "turbo"],
            ["low", "auto"],
        ),
        (
            Capability.THERMOSTAT_COOLING_SETPOINT,
            Attribute.COOLING_SETPOINT,
            23,
            ATTR_TEMPERATURE,
            25,
            23,
        ),
        (
            Capability.FAN_OSCILLATION_MODE,
            Attribute.FAN_OSCILLATION_MODE,
            "horizontal",
            ATTR_SWING_MODE,
            SWING_OFF,
            SWING_HORIZONTAL,
        ),
        (
            Capability.FAN_OSCILLATION_MODE,
            Attribute.FAN_OSCILLATION_MODE,
            "direct",
            ATTR_SWING_MODE,
            SWING_OFF,
            SWING_OFF,
        ),
    ],
    ids=[
        ATTR_CURRENT_TEMPERATURE,
        ATTR_FAN_MODE,
        ATTR_FAN_MODES,
        ATTR_TEMPERATURE,
        ATTR_SWING_MODE,
        f"{ATTR_SWING_MODE}_off",
    ],
)
async def test_ac_state_attributes_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    capability: Capability,
    attribute: Attribute,
    value: Any,
    state_attribute: str,
    original_value: Any,
    expected_value: Any,
) -> None:
    """Test state attributes update."""
    await setup_integration(hass, mock_config_entry)

    assert (
        hass.states.get("climate.ac_office_granit").attributes[state_attribute]
        == original_value
    )

    await trigger_update(
        hass,
        devices,
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        capability,
        attribute,
        value,
    )

    assert (
        hass.states.get("climate.ac_office_granit").attributes[state_attribute]
        == expected_value
    )


@pytest.mark.parametrize("device_fixture", ["virtual_thermostat"])
async def test_thermostat_set_fan_mode(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test thermostat set fan mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.asd", ATTR_FAN_MODE: "on"},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "2894dc93-0f11-49cc-8a81-3a684cebebf6",
        Capability.THERMOSTAT_FAN_MODE,
        Command.SET_THERMOSTAT_FAN_MODE,
        MAIN,
        argument="on",
    )


@pytest.mark.parametrize("device_fixture", ["virtual_thermostat"])
async def test_thermostat_set_hvac_mode(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test thermostat set HVAC mode."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.asd", ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
        blocking=True,
    )
    devices.execute_device_command.assert_called_once_with(
        "2894dc93-0f11-49cc-8a81-3a684cebebf6",
        Capability.THERMOSTAT_MODE,
        Command.SET_THERMOSTAT_MODE,
        MAIN,
        argument="auto",
    )


@pytest.mark.parametrize("device_fixture", ["virtual_thermostat"])
@pytest.mark.parametrize(
    ("state", "data", "calls"),
    [
        (
            "auto",
            {ATTR_TARGET_TEMP_LOW: 15, ATTR_TARGET_TEMP_HIGH: 23},
            [
                call(
                    "2894dc93-0f11-49cc-8a81-3a684cebebf6",
                    Capability.THERMOSTAT_HEATING_SETPOINT,
                    Command.SET_HEATING_SETPOINT,
                    MAIN,
                    argument=59.0,
                ),
                call(
                    "2894dc93-0f11-49cc-8a81-3a684cebebf6",
                    Capability.THERMOSTAT_COOLING_SETPOINT,
                    Command.SET_COOLING_SETPOINT,
                    MAIN,
                    argument=73.4,
                ),
            ],
        ),
        (
            "cool",
            {ATTR_TEMPERATURE: 15},
            [
                call(
                    "2894dc93-0f11-49cc-8a81-3a684cebebf6",
                    Capability.THERMOSTAT_COOLING_SETPOINT,
                    Command.SET_COOLING_SETPOINT,
                    MAIN,
                    argument=59.0,
                )
            ],
        ),
        (
            "heat",
            {ATTR_TEMPERATURE: 23},
            [
                call(
                    "2894dc93-0f11-49cc-8a81-3a684cebebf6",
                    Capability.THERMOSTAT_HEATING_SETPOINT,
                    Command.SET_HEATING_SETPOINT,
                    MAIN,
                    argument=73.4,
                )
            ],
        ),
        (
            "heat",
            {ATTR_TEMPERATURE: 23, ATTR_HVAC_MODE: HVACMode.COOL},
            [
                call(
                    "2894dc93-0f11-49cc-8a81-3a684cebebf6",
                    Capability.THERMOSTAT_MODE,
                    Command.SET_THERMOSTAT_MODE,
                    MAIN,
                    argument="cool",
                ),
                call(
                    "2894dc93-0f11-49cc-8a81-3a684cebebf6",
                    Capability.THERMOSTAT_COOLING_SETPOINT,
                    Command.SET_COOLING_SETPOINT,
                    MAIN,
                    argument=73.4,
                ),
            ],
        ),
    ],
)
async def test_thermostat_set_temperature(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    state: str,
    data: dict[str, Any],
    calls: list[call],
) -> None:
    """Test thermostat set temperature."""
    set_attribute_value(
        devices, Capability.THERMOSTAT_MODE, Attribute.THERMOSTAT_MODE, state
    )
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.asd"} | data,
        blocking=True,
    )
    assert devices.execute_device_command.mock_calls == calls


@pytest.mark.parametrize("device_fixture", ["virtual_thermostat"])
async def test_humidity(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test humidity extra state attribute."""
    devices.get_device_status.return_value[MAIN][
        Capability.RELATIVE_HUMIDITY_MEASUREMENT
    ] = {Attribute.HUMIDITY: Status(50)}
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.asd")
    assert state
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 50


@pytest.mark.parametrize("device_fixture", ["virtual_thermostat"])
async def test_updating_humidity(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test updating humidity extra state attribute."""
    devices.get_device_status.return_value[MAIN][
        Capability.RELATIVE_HUMIDITY_MEASUREMENT
    ] = {Attribute.HUMIDITY: Status(50)}
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.asd")
    assert state
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 50

    await trigger_update(
        hass,
        devices,
        "2894dc93-0f11-49cc-8a81-3a684cebebf6",
        Capability.RELATIVE_HUMIDITY_MEASUREMENT,
        Attribute.HUMIDITY,
        40,
    )

    assert hass.states.get("climate.asd").attributes[ATTR_CURRENT_HUMIDITY] == 40


@pytest.mark.parametrize("device_fixture", ["virtual_thermostat"])
@pytest.mark.parametrize(
    (
        "capability",
        "attribute",
        "value",
        "state_attribute",
        "original_value",
        "expected_value",
    ),
    [
        (
            Capability.TEMPERATURE_MEASUREMENT,
            Attribute.TEMPERATURE,
            20,
            ATTR_CURRENT_TEMPERATURE,
            4734.6,
            -6.7,
        ),
        (
            Capability.THERMOSTAT_FAN_MODE,
            Attribute.THERMOSTAT_FAN_MODE,
            "auto",
            ATTR_FAN_MODE,
            "followschedule",
            "auto",
        ),
        (
            Capability.THERMOSTAT_FAN_MODE,
            Attribute.SUPPORTED_THERMOSTAT_FAN_MODES,
            ["auto", "circulate"],
            ATTR_FAN_MODES,
            ["on"],
            ["auto", "circulate"],
        ),
        (
            Capability.THERMOSTAT_OPERATING_STATE,
            Attribute.THERMOSTAT_OPERATING_STATE,
            "fan only",
            ATTR_HVAC_ACTION,
            HVACAction.COOLING,
            HVACAction.FAN,
        ),
        (
            Capability.THERMOSTAT_MODE,
            Attribute.SUPPORTED_THERMOSTAT_MODES,
            ["rush hour", "heat"],
            ATTR_HVAC_MODES,
            [HVACMode.AUTO],
            [HVACMode.AUTO, HVACMode.HEAT],
        ),
    ],
    ids=[
        ATTR_CURRENT_TEMPERATURE,
        ATTR_FAN_MODE,
        ATTR_FAN_MODES,
        ATTR_HVAC_ACTION,
        ATTR_HVAC_MODES,
    ],
)
async def test_thermostat_state_attributes_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    capability: Capability,
    attribute: Attribute,
    value: Any,
    state_attribute: str,
    original_value: Any,
    expected_value: Any,
) -> None:
    """Test state attributes update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("climate.asd").attributes[state_attribute] == original_value

    await trigger_update(
        hass,
        devices,
        "2894dc93-0f11-49cc-8a81-3a684cebebf6",
        capability,
        attribute,
        value,
    )

    assert hass.states.get("climate.asd").attributes[state_attribute] == expected_value
