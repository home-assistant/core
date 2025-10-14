"""Test for the switchbot_cloud climate."""

from unittest.mock import patch

from switchbot_api import Remote, SmartRadiatorThermostatCommands

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, State

from . import configure_integration

from tests.common import mock_restore_cache


async def test_air_conditioner_set_hvac_mode(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test setting HVAC mode for air conditioner."""
    mock_list_devices.return_value = [
        Remote(
            deviceId="ac-device-id-1",
            deviceName="climate-1",
            remoteType="DIY Air Conditioner",
            hubDeviceId="test-hub-id",
        ),
    ]

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "climate.climate_1"

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: "cool"},
            blocking=True,
        )
        mock_send_command.assert_called_once()
        assert "21,2,1,on" in str(mock_send_command.call_args)

    assert hass.states.get(entity_id).state == "cool"

    # Test turning off
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: "off"},
            blocking=True,
        )
        mock_send_command.assert_called_once()
        assert "21,2,1,off" in str(mock_send_command.call_args)

    assert hass.states.get(entity_id).state == "off"


async def test_air_conditioner_set_fan_mode(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test setting fan mode for air conditioner."""
    mock_list_devices.return_value = [
        Remote(
            deviceId="ac-device-id-1",
            deviceName="climate-1",
            remoteType="Air Conditioner",
            hubDeviceId="test-hub-id",
        ),
    ]

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "climate.climate_1"

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: "high"},
            blocking=True,
        )
        mock_send_command.assert_called_once()
        assert "21,4,4,on" in str(mock_send_command.call_args)

    assert hass.states.get(entity_id).attributes[ATTR_FAN_MODE] == "high"


async def test_air_conditioner_set_temperature(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test setting temperature for air conditioner."""
    mock_list_devices.return_value = [
        Remote(
            deviceId="ac-device-id-1",
            deviceName="climate-1",
            remoteType="Air Conditioner",
            hubDeviceId="test-hub-id",
        ),
    ]

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "climate.climate_1"

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 25},
            blocking=True,
        )
        mock_send_command.assert_called_once()
        assert "25,4,1,on" in str(mock_send_command.call_args)

    assert hass.states.get(entity_id).attributes[ATTR_TEMPERATURE] == 25


async def test_air_conditioner_restore_state(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test restoring state for air conditioner."""
    mock_list_devices.return_value = [
        Remote(
            deviceId="ac-device-id-1",
            deviceName="climate-1",
            remoteType="Air Conditioner",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_state = State(
        "climate.climate_1",
        "cool",
        {
            ATTR_FAN_MODE: "high",
            ATTR_TEMPERATURE: 25,
        },
    )

    mock_restore_cache(hass, (mock_state,))
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = "climate.climate_1"
    state = hass.states.get(entity_id)
    assert state.state == "cool"
    assert state.attributes[ATTR_FAN_MODE] == "high"
    assert state.attributes[ATTR_TEMPERATURE] == 25


async def test_air_conditioner_no_last_state(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test behavior when no previous state exists."""
    mock_list_devices.return_value = [
        Remote(
            deviceId="ac-device-id-1",
            deviceName="climate-1",
            remoteType="Air Conditioner",
            hubDeviceId="test-hub-id",
        ),
    ]

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "climate.climate_1"
    state = hass.states.get(entity_id)
    assert state.state == "fan_only"
    assert state.attributes[ATTR_FAN_MODE] == "auto"
    assert state.attributes[ATTR_TEMPERATURE] == 21


async def test_air_conditioner_turn_off(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test the climate.turn_off service."""
    mock_list_devices.return_value = [
        Remote(
            deviceId="ac-device-id-1",
            deviceName="climate-1",
            remoteType="DIY Air Conditioner",
            hubDeviceId="test-hub-id",
        ),
    ]

    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "climate.climate_1"
    assert hass.states.get(entity_id).state == "fan_only"

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_send_command.assert_called_once()
        assert "21,4,1,off" in str(mock_send_command.call_args)

    assert hass.states.get(entity_id).state == "off"


async def test_air_conditioner_turn_on(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning on a climate entity that has a non-off HVAC_STATE."""
    mock_list_devices.return_value = [
        Remote(
            deviceId="ac-device-id-1",
            deviceName="climate-1",
            remoteType="DIY Air Conditioner",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_state = State(
        "climate.climate_1",
        "cool",
        {
            ATTR_FAN_MODE: "high",
            ATTR_TEMPERATURE: 25,
        },
    )
    mock_restore_cache(hass, (mock_state,))
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "climate.climate_1"
    assert hass.states.get(entity_id).state == "cool"

    with patch.object(SwitchBotAPI, "send_command") as mock_turn_on_command:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_turn_on_command.assert_called_once()
        assert "25,2,4,on" in str(mock_turn_on_command.call_args)

    assert hass.states.get(entity_id).state == "cool"


async def test_air_conditioner_turn_on_from_hvac_mode_off(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test turning on a climate entity that has an off HVAC_STATE."""
    mock_list_devices.return_value = [
        Remote(
            deviceId="ac-device-id-1",
            deviceName="climate-1",
            remoteType="DIY Air Conditioner",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_state = State(
        "climate.climate_1",
        "off",
        {
            ATTR_FAN_MODE: "high",
            ATTR_TEMPERATURE: 25,
        },
    )
    mock_restore_cache(hass, (mock_state,))
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "climate.climate_1"
    assert hass.states.get(entity_id).state == "off"

    with patch.object(SwitchBotAPI, "send_command") as mock_turn_on_command:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_turn_on_command.assert_called_once()
        assert "25,4,4,on" in str(mock_turn_on_command.call_args)

    assert hass.states.get(entity_id).state == "fan_only"


async def test_smart_radiator_thermostat_set_temperature(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test smart radiator thermostat set temperature."""
    mock_list_devices.return_value = [
        Remote(
            deviceId="ac-device-id-1",
            deviceName="climate-1",
            remoteType="Smart Radiator Thermostat",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "mode": 1,
            "temperature": 27.5,
        },
        {
            "mode": 1,
            "temperature": 27.5,
        },
        {
            "mode": 2,
            "temperature": 27.5,
        },
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    entity_id = "climate.climate_1"

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, "temperature": 27},
        )
    mock_send_command.assert_called_once_with(
        "ac-device-id-1",
        SmartRadiatorThermostatCommands.SET_MANUAL_MODE_TEMPERATURE,
        "command",
        "27.0",
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, "temperature": 4},
        )
    mock_send_command.assert_called_once_with(
        "ac-device-id-1", SmartRadiatorThermostatCommands.SET_MODE, "command", 2
    )
