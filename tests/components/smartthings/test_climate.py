"""Test for the SmartThings climate platform."""

from unittest.mock import AsyncMock, call

from pysmartthings.models import Attribute, Capability, Command
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_OFF,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import set_attribute_value, setup_integration, snapshot_smartthings_entities

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


@pytest.mark.parametrize("fixture", ["da_ac_rac_000001"])
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
        argument="auto",
    )


@pytest.mark.parametrize("fixture", ["da_ac_rac_000001"])
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
    )


@pytest.mark.parametrize("fixture", ["da_ac_rac_000001"])
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
        argument=argument,
    )


@pytest.mark.parametrize("fixture", ["da_ac_rac_000001"])
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
            Capability.AIR_CONDITIONER_MODE,
            Command.SET_AIR_CONDITIONER_MODE,
            argument="auto",
        ),
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.SWITCH,
            Command.ON,
        ),
    ]


@pytest.mark.parametrize("fixture", ["da_ac_rac_000001"])
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
        argument="wind",
    )


@pytest.mark.parametrize("fixture", ["da_ac_rac_000001"])
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
        argument=23,
    )


@pytest.mark.parametrize("fixture", ["da_ac_rac_000001"])
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
            Capability.THERMOSTAT_COOLING_SETPOINT,
            Command.SET_COOLING_SETPOINT,
            argument=23.0,
        ),
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.SWITCH,
            Command.ON,
        ),
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.AIR_CONDITIONER_MODE,
            Command.SET_AIR_CONDITIONER_MODE,
            argument="auto",
        ),
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.SWITCH,
            Command.ON,
        ),
    ]


@pytest.mark.parametrize("fixture", ["da_ac_rac_000001"])
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
            argument=23.0,
        ),
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.AIR_CONDITIONER_MODE,
            Command.SET_AIR_CONDITIONER_MODE,
            argument="auto",
        ),
    ]


@pytest.mark.parametrize("fixture", ["da_ac_rac_000001"])
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
            Capability.THERMOSTAT_COOLING_SETPOINT,
            Command.SET_COOLING_SETPOINT,
            argument=23.0,
        ),
        call(
            "96a5ef74-5832-a84b-f1f7-ca799957065d",
            Capability.SWITCH,
            Command.OFF,
        ),
    ]


@pytest.mark.parametrize("fixture", ["da_ac_rac_000001"])
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
        "96a5ef74-5832-a84b-f1f7-ca799957065d", Capability.SWITCH, command
    )


@pytest.mark.parametrize("fixture", ["da_ac_rac_000001"])
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
        argument="fixed",
    )


@pytest.mark.parametrize("fixture", ["da_ac_rac_000001"])
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
        argument="windFree",
    )
