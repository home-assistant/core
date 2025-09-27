"""Test code Support for water heater entity."""

from unittest.mock import patch

from switchbot_api import (
    Device,
    SmartRadiatorThermostatCommands,
    SmartRadiatorThermostatMode,
)

from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_coordinator_data_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test coordinator data is none."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="water_heater-id-1",
            deviceName="water_heater-1",
            deviceType="Smart Radiator Thermostat",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        None,
    ]
    await configure_integration(hass)
    entity_id = "water_heater.water_heater_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_UNKNOWN


async def test_set_temperature(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test set temperature."""

    mock_list_devices.side_effect = [
        [
            Device(
                version="V1.0",
                deviceId="water-heater-id-1",
                deviceName="water_heater-1",
                deviceType="Smart Radiator Thermostat",
                hubDeviceId="test-hub-id",
            ),
        ]
    ]
    mock_get_status.side_effect = [
        {
            "version": "V0.6",
            "temperature": 21,
            "battery": 90,
            "mode": 1,
            "deviceId": "B0E9FEA2547C",
            "deviceType": "Smart Radiator Thermostat",
            "hubDeviceId": "000000000000",
        },
    ]

    await configure_integration(hass)
    entity_id = "water_heater.water_heater_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, "temperature": 21},
        )
        mock_send_command.assert_called_once_with(
            "water-heater-id-1",
            SmartRadiatorThermostatCommands.SET_MANUAL_MODE_TEMPERATURE,
            "command",
            "21.0",
        )


async def test_set_mode(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test set mode."""

    mock_list_devices.side_effect = [
        [
            Device(
                version="V1.0",
                deviceId="water-heater-id-1",
                deviceName="water_heater-1",
                deviceType="Smart Radiator Thermostat",
                hubDeviceId="test-hub-id",
            ),
        ]
    ]
    mock_get_status.side_effect = [
        {
            "version": "V0.6",
            "temperature": 21,
            "battery": 90,
            "mode": 2,
            "deviceId": "B0E9FEA2547C",
            "deviceType": "Smart Radiator Thermostat",
            "hubDeviceId": "000000000000",
        },
    ]

    await configure_integration(hass)
    entity_id = "water_heater.water_heater_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_OPERATION_MODE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_OPERATION_MODE: SmartRadiatorThermostatMode.OFF.name,
            },
        )
        mock_send_command.assert_called_once_with(
            "water-heater-id-1",
            SmartRadiatorThermostatCommands.SET_MODE,
            "command",
            str(SmartRadiatorThermostatMode.OFF.value),
        )
