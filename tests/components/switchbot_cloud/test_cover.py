"""Test for the switchbot_cloud Cover."""

from unittest.mock import patch

import pytest
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
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_cover_set_attributes_normal(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test cover set_attributes normal."""
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
    assert state.state == STATE_CLOSED


@pytest.mark.parametrize(
    "device_model",
    [
        "Roller Shade",
        "Blind Tilt",
    ],
)
async def test_cover_set_attributes_position_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status, device_model
) -> None:
    """Test cover_set_attributes position is none."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType=device_model,
            hubDeviceId="test-hub-id",
        ),
    ]

    cover_id = "cover.cover_1"
    mock_get_status.side_effect = [{"direction": "up"}, {"direction": "up"}]
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "device_model",
    [
        "Roller Shade",
        "Blind Tilt",
    ],
)
async def test_cover_set_attributes_coordinator_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status, device_model
) -> None:
    """Test cover set_attributes coordinator is none."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType=device_model,
            hubDeviceId="test-hub-id",
        ),
    ]

    cover_id = "cover.cover_1"
    mock_get_status.return_value = None
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_UNKNOWN


async def test_curtain_features(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test curtain features."""
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
            "slidePosition": 95,
        },
        {
            "slidePosition": 95,
        },
        {
            "slidePosition": 95,
        },
        {
            "slidePosition": 95,
        },
        {
            "slidePosition": 95,
        },
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

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", CurtainCommands.PAUSE, "command", "default"
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {"position": 50, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", CurtainCommands.SET_POSITION, "command", "0,ff,50"
    )


@pytest.mark.parametrize(
    ("slide_position", "expected_state", "expected_tilt"),
    [
        (0, STATE_CLOSED, 0),  # closed down
        (19, STATE_CLOSED, 19),
        (20, STATE_OPEN, 20),
        (50, STATE_OPEN, 50),  # horizontal/open
        (80, STATE_OPEN, 80),
        (81, STATE_CLOSED, 81),
        (100, STATE_CLOSED, 100),  # closed up
    ],
)
async def test_blind_tilt_set_attributes_states(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    slide_position: int,
    expected_state: str,
    expected_tilt: int,
) -> None:
    """Test blind tilt state and tilt position at various slidePosition values.

    slidePosition uses the physical scale: 0=closed down, 50=open, 100=closed up.
    Passed through directly as HA tilt. is_closed: position < 20 or position > 80.
    """
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
    mock_get_status.return_value = {"slidePosition": slide_position, "direction": "up"}
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == expected_state
    assert state.attributes.get("current_tilt_position") == expected_tilt


async def test_blind_tilt_features(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test blind_tilt features."""
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
        {"slidePosition": 95, "direction": "up"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cover_id = "cover.cover_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.FULLY_OPEN, "command", "default"
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.CLOSE_UP, "command", "default"
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            # HA 75 = physical 75 (up half): direction "up", cmd (100-75)*2=50
            {"tilt_position": 75, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.SET_POSITION, "command", "up;50"
    )


async def test_blind_tilt_features_close_down(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test blind tilt features close_down."""
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
        {"slidePosition": 25, "direction": "down"},
        {"slidePosition": 25, "direction": "down"},
        {"slidePosition": 25, "direction": "down"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cover_id = "cover.cover_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.CLOSE_DOWN, "command", "default"
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            # HA 25 = physical 25 (down half): direction "down", cmd 25*2=50
            {"tilt_position": 25, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.SET_POSITION, "command", "down;50"
    )


async def test_roller_shade_features(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test roller shade features."""
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
        "cover-id-1", RollerShadeCommands.SET_POSITION, "command", 0
    )

    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_OPEN

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", RollerShadeCommands.SET_POSITION, "command", 100
    )

    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_OPEN

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {"position": 50, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", RollerShadeCommands.SET_POSITION, "command", 50
    )


async def test_cover_set_attributes_coordinator_is_none_for_garage_door(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test cover set_attributes coordinator is none for garage_door."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Garage Door Opener",
            hubDeviceId="test-hub-id",
        ),
    ]
    cover_id = "cover.cover_1"
    mock_get_status.return_value = None
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_UNKNOWN


async def test_garage_door_features_close(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test garage door features close."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Garage Door Opener",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "doorStatus": 1,
        },
        {
            "doorStatus": 1,
        },
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cover_id = "cover.cover_1"
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

    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_CLOSED


async def test_garage_door_features_open(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test garage_door features open cover."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Garage Door Opener",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "doorStatus": 0,
        },
        {
            "doorStatus": 0,
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
        "cover-id-1", CommonCommands.ON, "command", "default"
    )

    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_OPEN
