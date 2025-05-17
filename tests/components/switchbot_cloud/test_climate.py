"""Test for the switchbot_cloud relay switch & bot."""

from unittest.mock import patch

from switchbot_api import Remote

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.components.switchbot_cloud.climate import RestoreEntity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, State

from . import configure_integration


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
            {ATTR_ENTITY_ID: entity_id, "fan_mode": "high"},
            blocking=True,
        )
        mock_send_command.assert_called_once()
        assert "21,4,4,on" in str(mock_send_command.call_args)

    assert hass.states.get(entity_id).attributes["fan_mode"] == "high"


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
            {ATTR_ENTITY_ID: entity_id, "temperature": 25},
            blocking=True,
        )
        mock_send_command.assert_called_once()
        assert "25,4,1,on" in str(mock_send_command.call_args)

    assert hass.states.get(entity_id).attributes["temperature"] == 25


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
            "fan_mode": "high",
            "temperature": 25,
        },
    )

    with patch.object(
        RestoreEntity,
        "async_get_last_state",
        return_value=mock_state,
    ):
        entry = await configure_integration(hass)
        assert entry.state is ConfigEntryState.LOADED
        entity_id = "climate.climate_1"
        state = hass.states.get(entity_id)
        assert state.state == "cool"
        assert state.attributes["fan_mode"] == "high"
        assert state.attributes["temperature"] == 25


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
    assert state.attributes["fan_mode"] == "auto"
    assert state.attributes["temperature"] == 21
