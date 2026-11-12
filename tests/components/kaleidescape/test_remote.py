"""Tests for Kaleidescape remote platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.remote import (
    ATTR_COMMAND,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import MOCK_SERIAL

ENTITY_ID = f"remote.theater_kaleidescape_device_{MOCK_SERIAL}"


@pytest.mark.usefixtures("mock_device", "mock_integration")
async def test_entity(hass: HomeAssistant) -> None:
    """Test entity attributes."""
    assert hass.states.get(ENTITY_ID)


@pytest.mark.parametrize(
    ("service", "method"),
    [
        pytest.param(SERVICE_TURN_ON, "leave_standby", id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, "enter_standby", id="turn_off"),
    ],
)
@pytest.mark.usefixtures("mock_integration")
async def test_turn_on_off(
    hass: HomeAssistant, mock_device: MagicMock, service: str, method: str
) -> None:
    """Test turning the device on and off."""
    await hass.services.async_call(
        REMOTE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    getattr(mock_device, method).assert_awaited_once_with()


@pytest.mark.parametrize(
    "command",
    [
        "select",
        "up",
        "down",
        "left",
        "right",
        "cancel",
        "play",
        "pause",
        "stop",
        "next",
        "previous",
        "replay",
        "scan_forward",
        "scan_reverse",
        "intermission_toggle",
        "status_and_settings",
        "go_movies",
        "go_movie_covers",
        "go_movie_list",
        "go_movie_collections",
        "menu_toggle",
    ],
)
@pytest.mark.usefixtures("mock_integration")
async def test_send_command(
    hass: HomeAssistant, mock_device: MagicMock, command: str
) -> None:
    """Test each command calls the device method of the same name."""
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COMMAND: [command]},
        blocking=True,
    )
    getattr(mock_device, command).assert_awaited_once_with()


@pytest.mark.usefixtures("mock_device", "mock_integration")
async def test_unknown_command(hass: HomeAssistant) -> None:
    """Test service calls."""
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_COMMAND: ["bad"]},
            blocking=True,
        )
    assert str(err.value) == "bad is not a known command"
