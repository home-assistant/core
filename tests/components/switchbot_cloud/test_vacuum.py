"""Test for the switchbot_cloud vacuum."""

from unittest.mock import patch

from switchbot_api import (
    Device,
    VacuumCleanerV2Commands,
    VacuumCleanerV3Commands,
    VacuumCleanMode,
    VacuumCommands,
)

from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.components.switchbot_cloud.const import VACUUM_FAN_SPEED_QUIET
from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    VacuumActivity,
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
            deviceId="vacuum-id-1",
            deviceName="vacuum-1",
            deviceType="K10+",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.side_effect = [
        None,
    ]
    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    state = hass.states.get(entity_id)

    assert state.state == STATE_UNKNOWN


async def test_k10_plus_set_fan_speed(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test K10 plus set fan speed."""

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
            "deviceType": "K10+",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_SET_FAN_SPEED,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_SPEED: VACUUM_FAN_SPEED_QUIET},
            blocking=True,
        )
        mock_send_command.assert_called_once_with(
            "vacuum-id-1", VacuumCommands.POW_LEVEL, "command", "0"
        )


async def test_k10_plus_return_to_base(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test k10 plus return to base."""
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
            VACUUM_DOMAIN,
            SERVICE_RETURN_TO_BASE,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_send_command.assert_called_once_with(
            "vacuum-id-1", VacuumCommands.DOCK, "command", "default"
        )


async def test_k10_plus_pause(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test k10 plus pause."""
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
            VACUUM_DOMAIN, SERVICE_PAUSE, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called_once_with(
            "vacuum-id-1", VacuumCommands.STOP, "command", "default"
        )


async def test_k10_plus_set_start(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test K10 plus start."""

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
            "deviceType": "K10+",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_START,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_send_command.assert_called_once_with(
            "vacuum-id-1", VacuumCommands.START, "command", "default"
        )


async def test_k20_plus_pro_set_fan_speed(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test K10 plus set fan speed."""

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
            VACUUM_DOMAIN,
            SERVICE_SET_FAN_SPEED,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_SPEED: VACUUM_FAN_SPEED_QUIET},
            blocking=True,
        )
        mock_send_command.assert_called_once_with(
            "vacuum-id-1",
            VacuumCleanerV2Commands.CHANGE_PARAM,
            "command",
            {
                "fanLevel": 1,
                "waterLevel": 1,
                "times": 1,
            },
        )


async def test_k20_plus_pro_return_to_base(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test K20+ Pro return to base."""
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
            SERVICE_RETURN_TO_BASE,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_send_command.assert_called_once_with(
            "vacuum-id-1", VacuumCleanerV2Commands.DOCK, "command", "default"
        )


async def test_k20_plus_pro_pause(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test K20+ Pro pause."""
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
            VACUUM_DOMAIN, SERVICE_PAUSE, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_send_command.assert_called_once_with(
            "vacuum-id-1", VacuumCleanerV2Commands.PAUSE, "command", "default"
        )


async def test_k20_plus_pro_start(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test K20+ Pro start."""

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
            VACUUM_DOMAIN,
            SERVICE_START,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_send_command.assert_called_once_with(
            "vacuum-id-1",
            VacuumCleanerV2Commands.START_CLEAN,
            "command",
            {
                "action": VacuumCleanMode.SWEEP.value,
                "param": {
                    "fanLevel": 1,
                    "times": 1,
                },
            },
        )


async def test_k10_plus_pro_combo_set_fan_speed(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test k10+ Pro Combo set fan speed."""

    mock_list_devices.side_effect = [
        [
            Device(
                version="V1.0",
                deviceId="vacuum-id-1",
                deviceName="vacuum-1",
                deviceType="Robot Vacuum Cleaner K10+ Pro Combo",
                hubDeviceId="test-hub-id",
            )
        ]
    ]
    mock_get_status.side_effect = [
        {
            "deviceType": "Robot Vacuum Cleaner K10+ Pro Combo",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_SET_FAN_SPEED,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_SPEED: VACUUM_FAN_SPEED_QUIET},
            blocking=True,
        )
        mock_send_command.assert_called_once_with(
            "vacuum-id-1",
            VacuumCleanerV2Commands.CHANGE_PARAM,
            "command",
            {
                "fanLevel": 1,
                "times": 1,
            },
        )


async def test_s20_start(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test s20 start."""

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
            "deviceType": "s20",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_START,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_send_command.assert_called_once_with(
            "vacuum-id-1",
            VacuumCleanerV3Commands.START_CLEAN,
            "command",
            {
                "action": VacuumCleanMode.SWEEP.value,
                "param": {
                    "fanLevel": 0,
                    "waterLevel": 1,
                    "times": 1,
                },
            },
        )


async def test_s20set_fan_speed(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test s20 set fan speed."""

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
            "deviceType": "S20",
            "workingStatus": "Cleaning",
            "battery": 50,
            "onlineStatus": "online",
        },
    ]

    await configure_integration(hass)
    entity_id = "vacuum.vacuum_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_SET_FAN_SPEED,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_SPEED: VACUUM_FAN_SPEED_QUIET},
            blocking=True,
        )
        mock_send_command.assert_called_once_with(
            "vacuum-id-1",
            VacuumCleanerV3Commands.CHANGE_PARAM,
            "command",
            {
                "fanLevel": 1,
                "waterLevel": 1,
                "times": 1,
            },
        )
