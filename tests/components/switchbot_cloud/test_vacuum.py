"""Test for the switchbot_cloud vacuum."""

from unittest.mock import patch

from switchbot_api import Device

from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN, VacuumActivity
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_start(hass: HomeAssistant, mock_list_devices, mock_get_status) -> None:
    """Test locking and unlocking."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="vacuum-id-1",
            deviceName="vacuum-1",
            deviceType="K10+",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "deviceType": "K10+",
            "workingStatus": "Charging",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "K10+",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "K10+",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    state = hass.states.get(entity_id)

    assert state.state == VacuumActivity.DOCKED.value

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, "start", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called()


async def test_return_to_base(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test locking and unlocking."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="vacuum-id-1",
            deviceName="vacuum-1",
            deviceType="K10+",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "deviceType": "K10+",
            "workingStatus": "Charging",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "K10+",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "K10+",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    state = hass.states.get(entity_id)

    assert state.state == VacuumActivity.DOCKED.value

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, "return_to_base", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called()


async def test_pause(hass: HomeAssistant, mock_list_devices, mock_get_status) -> None:
    """Test locking and unlocking."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="vacuum-id-1",
            deviceName="vacuum-1",
            deviceType="K10+",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "deviceType": "K10+",
            "workingStatus": "Charging",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "K10+",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "K10+",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    state = hass.states.get(entity_id)

    assert state.state == VacuumActivity.DOCKED.value

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, "pause", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called()


async def test_set_fan_speed(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test locking and unlocking."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="vacuum-id-1",
            deviceName="vacuum-1",
            deviceType="K10+",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "deviceType": "K10+",
            "workingStatus": "Charging",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "K10+",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "K10+",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    state = hass.states.get(entity_id)

    assert state.state == VacuumActivity.DOCKED.value

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            "set_fan_speed",
            {ATTR_ENTITY_ID: entity_id, "fan_speed": "quiet"},
            blocking=True,
        )
        mock_send_command.assert_called()


async def test_start_v2(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test locking and unlocking."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="vacuum-id-1",
            deviceName="vacuum-1",
            deviceType="S20",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "deviceType": "S20",
            "workingStatus": "Charging",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "S20",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "S20",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    state = hass.states.get(entity_id)

    assert state.state == VacuumActivity.DOCKED.value

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, "start", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called()


async def test_return_to_base_v2(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test locking and unlocking."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="vacuum-id-1",
            deviceName="vacuum-1",
            deviceType="S20",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "deviceType": "S20",
            "workingStatus": "Charging",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "S20",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "S20",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    state = hass.states.get(entity_id)

    assert state.state == VacuumActivity.DOCKED.value

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, "return_to_base", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called()


async def test_pause_v2(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test locking and unlocking."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="vacuum-id-1",
            deviceName="vacuum-1",
            deviceType="S20",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "deviceType": "S20",
            "workingStatus": "Charging",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "S20",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "S20",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    state = hass.states.get(entity_id)

    assert state.state == VacuumActivity.DOCKED.value

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, "pause", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called()


async def test_set_fan_speed_v2(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test locking and unlocking."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="vacuum-id-1",
            deviceName="vacuum-1",
            deviceType="S20",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "deviceType": "S20",
            "workingStatus": "Charging",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "S20",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
        {
            "deviceType": "S20",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    state = hass.states.get(entity_id)

    assert state.state == VacuumActivity.DOCKED.value

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            "set_fan_speed",
            {ATTR_ENTITY_ID: entity_id, "fan_speed": "quiet"},
            blocking=True,
        )
        mock_send_command.assert_called()
