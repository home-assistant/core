"""Test for the switchbot_cloud vacuum."""

from unittest.mock import patch

from switchbot_api import Device

from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN, VacuumActivity
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_start1(hass: HomeAssistant, mock_list_devices, mock_get_status) -> None:
    """Test locking and unlocking."""

    mock_list_devices.side_effect = [
        [
            Device(
                version="V1.0",
                deviceId="vacuum-id-1",
                deviceName="vacuum-1",
                deviceType="K10+",
                hubDeviceId="test-hub-id",
            )
        ]
    ]
    mock_get_status.side_effect = [
        {
            "deviceType": "K20+ Pro",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, "start", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called_once()


async def test_start2(hass: HomeAssistant, mock_list_devices, mock_get_status) -> None:
    """Test locking and unlocking."""

    mock_list_devices.side_effect = [
        [
            Device(
                version="V1.0",
                deviceId="vacuum-id-1",
                deviceName="vacuum-1",
                deviceType="K20+ Pro",
                hubDeviceId="test-hub-id",
            )
        ]
    ]
    mock_get_status.side_effect = [
        {
            "deviceType": "K20+ Pro",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, "start", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called_once()


async def test_start3(hass: HomeAssistant, mock_list_devices, mock_get_status) -> None:
    """Test locking and unlocking."""

    mock_list_devices.side_effect = [
        [
            Device(
                version="V1.0",
                deviceId="vacuum-id-1",
                deviceName="vacuum-1",
                deviceType="S20",
                hubDeviceId="test-hub-id",
            )
        ]
    ]
    mock_get_status.side_effect = [
        {
            "deviceType": "K20+ Pro",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]
    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN, "start", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called_once()


async def test_return_to_base1(
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
        }
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


async def test_return_to_base2(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test locking and unlocking."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="vacuum-id-1",
            deviceName="vacuum-1",
            deviceType="K20+ Pro",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "deviceType": "K10+",
            "workingStatus": "Charging",
            "battery": 50,
            "onlineStatus": "online",
        }
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


async def test_return_to_base3(
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
            "deviceType": "K10+",
            "workingStatus": "Charging",
            "battery": 50,
            "onlineStatus": "online",
        }
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


async def test_pause_1(hass: HomeAssistant, mock_list_devices, mock_get_status) -> None:
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
        }
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


async def test_pause_2(hass: HomeAssistant, mock_list_devices, mock_get_status) -> None:
    """Test locking and unlocking."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="vacuum-id-1",
            deviceName="vacuum-1",
            deviceType="K20+ Pro",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "deviceType": "K10+",
            "workingStatus": "Charging",
            "battery": 50,
            "onlineStatus": "online",
        }
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


async def test_pause_3(hass: HomeAssistant, mock_list_devices, mock_get_status) -> None:
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
            "deviceType": "K10+",
            "workingStatus": "Charging",
            "battery": 50,
            "onlineStatus": "online",
        }
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


async def test_set_fan_speed1(
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


async def test_set_fan_speed2(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test locking and unlocking."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="vacuum-id-1",
            deviceName="vacuum-1",
            deviceType="K20+ Pro",
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


async def test_set_fan_speed3(
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
            "deviceType": "K10+",
            "workingStatus": "Charging",
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
