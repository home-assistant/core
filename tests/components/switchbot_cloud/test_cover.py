"""Test for the switchbot_cloud Cover."""

from unittest.mock import patch

from switchbot_api import (
    BlindTiltCommands,
    CommonCommands,
    CurtainCommands,
    Device,
    RollerShadeCommands,
)

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
)
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_set_attributes(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_set_attributes."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Roller Shade",
            hubDeviceId="test-hub-id",
        ),
    ]

    cover_id = "cover.cover_1"
    mock_get_status.return_value = {"slidePosition": 100, "direction": "up"}
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == "closed"


async def test_set_attributes_coordinator_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_set_attributes_coordinator_is_none."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Roller Shade",
            hubDeviceId="test-hub-id",
        ),
    ]

    cover_id = "cover.cover_1"
    mock_get_status.return_value = None
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == "unknown"


async def test_set_attributes_position_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_set_attributes_position_is_none."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Roller Shade",
            hubDeviceId="test-hub-id",
        ),
    ]

    cover_id = "cover.cover_1"
    mock_get_status.return_value = {}
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == "unknown"


async def test_curtain_async_open_and_close_cover(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_curtain_async_open_and_close_cover."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Curtain",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "slidePosition": 95,
        },
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cover_id = "cover.cover_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    assert hass.states.get(cover_id).state in "open"
    mock_send_command.assert_called_once_with(
        "cover-id-1", CommonCommands.ON, "command", "default"
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", CommonCommands.OFF, "command", "default"
    )


async def test_curtain_set_cover_position_pause(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_curtain_set_cover_position_pause."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Curtain",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "slidePosition": 95,
        },
        {
            "slidePosition": 85,
        },
        {},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cover_id = "cover.cover_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {"position": 50, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    assert hass.states.get(cover_id).state in "open"
    mock_send_command.assert_called_once()

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    state = hass.states.get(cover_id)
    assert state.state == "open"
    mock_send_command.assert_called_once_with(
        "cover-id-1", CurtainCommands.PAUSE, "command", "default"
    )


async def test_curtain_stop_and_position_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_curtain_stop_and_position_is_none."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Curtain",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "slidePosition": 95,
        },
        {},
    ]
    cover_id = "cover.cover_1"
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    state = hass.states.get(cover_id)
    assert state.state == "open"
    mock_send_command.assert_called_once_with(
        "cover-id-1", CurtainCommands.PAUSE, "command", "default"
    )


async def test_tilt_set_position(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_tilt_set_position."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {"slidePosition": 95, "direction": "up"},
        {"slidePosition": 55, "direction": "up"},
    ]
    cover_id = "cover.cover_1"
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            {"tilt_position": 55, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    state = hass.states.get(cover_id)
    assert state.state == "open"
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.SET_POSITION, "command", "up;55"
    )


async def test_tilt_open_cover(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_tilt_open_cover."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {"slidePosition": 55, "direction": "up"},
        {"slidePosition": 55, "direction": "up"},
    ]
    cover_id = "cover.cover_1"
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    state = hass.states.get(cover_id)
    assert state.state == "open"
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.FULLY_OPEN, "command", "default"
    )


async def test_tilt_close_cover_1(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_tilt_close_cover."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {"slidePosition": 55, "direction": "up"},
        {"slidePosition": 45, "direction": "down"},
    ]
    cover_id = "cover.cover_1"
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    state = hass.states.get(cover_id)
    assert state.state == "open"
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.CLOSE_UP, "command", "default"
    )


async def test_tilt_close_cover_2(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_tilt_close_cover."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {"slidePosition": 45, "direction": "down"},
        {"slidePosition": 55, "direction": "up"},
    ]
    cover_id = "cover.cover_1"
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    state = hass.states.get(cover_id)
    assert state.state == "open"
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.CLOSE_DOWN, "command", "default"
    )


async def test_tilt_set_attributes_coordinator_data_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_tilt_set_attributes_coordinator_data_is_none."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]

    cover_id = "cover.cover_1"
    mock_get_status.return_value = None
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == "unknown"


async def test_tilt_set_attributes_position_is_not_none_1(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_tilt_set_attributes_position_is_not_none_1."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]

    cover_id = "cover.cover_1"
    mock_get_status.return_value = {"slidePosition": 55, "direction": "down"}
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == "open"


async def test_tilt_set_attributes_position_is_not_none_2(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_tilt_set_attributes_position_is_not_none_2."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]

    cover_id = "cover.cover_1"
    mock_get_status.return_value = {
        "slidePosition": 45,
    }
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == "open"


async def test_roller_shade_async_open_and_close_cover(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_roller_shade_async_open_and_close_cover."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Roller Shade",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "slidePosition": 95,
        },
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cover_id = "cover.cover_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", RollerShadeCommands.SET_POSITION, "command", "0"
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", RollerShadeCommands.SET_POSITION, "command", "100"
    )


async def test_roller_shade_set_cover_position(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_roller_shade_set_cover_position."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Roller Shade",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "slidePosition": 95,
        },
        {
            "slidePosition": 85,
        },
        {},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cover_id = "cover.cover_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {"position": 50, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    assert hass.states.get(cover_id).state in "open"
    mock_send_command.assert_called_once()
