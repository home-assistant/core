"""Test for the switchbot_cloud Cover."""

from unittest.mock import patch

from switchbot_api import Device

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


async def test_set_attributes_coordinator_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_set_attributes_coordinator_is_none."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Curtain",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [None, None]

    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED


async def test_BlindTilt_set_attributes_coordinator_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_set_attributes_coordinator_is_none."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [None, None]

    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED


async def test_Roller_Shade_set_attributes_coordinator_is_none(
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

    mock_get_status.side_effect = [None, None]

    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED


async def test_set_attributes_position_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_set_attributes_position_is_none."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Curtain",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [{}, {}]

    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED


async def test_set_attributes_position_is_0(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_set_attributes_position_is_0."""
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
            "slidePosition": 0,
        },
        {"slidePosition": 0},
    ]

    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED


async def test_set_attributes_position_is_100(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_set_attributes_position_is_100."""
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
        {"slidePosition": 100, "direction": "up"},
        {"slidePosition": 100, "direction": "up"},
    ]

    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED


async def test_curtain(hass: HomeAssistant, mock_list_devices, mock_get_status) -> None:
    """test_curtain."""
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
            "slidePosition": 100,
        },
        {
            "slidePosition": 100,
        },
        {
            "slidePosition": 100,
        },
        {
            "slidePosition": 100,
        },
    ]

    cover_id = "cover.cover_1"
    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED
    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: cover_id}, blocking=True
        )
    assert hass.states.get(cover_id).state == "closed"

    assert entry.state is ConfigEntryState.LOADED
    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: cover_id}, blocking=True
        )
    assert hass.states.get(cover_id).state == "open"


async def test_curtain_set_position(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_curtain_set_position."""
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
            "slidePosition": 100,
        },
        {
            "slidePosition": 100,
        },
        {
            "slidePosition": 100,
        },
        {
            "slidePosition": 100,
        },
    ]

    cover_id = "cover.cover_1"
    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED
    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {"position": 0, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    assert hass.states.get(cover_id).state == "closed"

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {"position": 50, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    assert hass.states.get(cover_id).state == "open"


async def test_curtain_pause(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_curtain_pause."""
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
            "slidePosition": 0,
        },
        {
            "slidePosition": 100,
        },
        {
            "slidePosition": 0,
        },
        {},
    ]

    cover_id = "cover.cover_1"
    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED
    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: cover_id}, blocking=True
        )
    assert hass.states.get(cover_id).state == "open"

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: cover_id}, blocking=True
        )
    assert hass.states.get(cover_id).state == "closed"

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: cover_id}, blocking=True
        )
    assert hass.states.get(cover_id).state == "closed"


async def test_tilt(hass: HomeAssistant, mock_list_devices, mock_get_status) -> None:
    """test_tilt."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"slidePosition": 0, "direction": "up"}

    cover_id = "cover.cover_1"
    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            {"tilt_position": 50, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    assert hass.states.get(cover_id).state == "closed"

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )

    assert hass.states.get(cover_id).state == "closed"

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    assert hass.states.get(cover_id).state == "open"


async def test_tilt_1(hass: HomeAssistant, mock_list_devices, mock_get_status) -> None:
    """test_tilt."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"slidePosition": 100, "direction": "down"}

    cover_id = "cover.cover_1"
    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    assert hass.states.get(cover_id).state == "closed"


async def test_roller_shade(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """test_tilt."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Roller Shade",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.return_value = {"slidePosition": 0, "direction": "up"}

    cover_id = "cover.cover_1"
    entry = await configure_integration(hass)

    assert entry.state is ConfigEntryState.LOADED

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {"position": 50, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    assert hass.states.get(cover_id).state == "open"

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: cover_id}, blocking=True
        )

    assert hass.states.get(cover_id).state == "open"

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: cover_id}, blocking=True
        )
    assert hass.states.get(cover_id).state == "closed"
