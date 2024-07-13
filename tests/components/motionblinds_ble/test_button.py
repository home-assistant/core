"""Tests for Motionblinds BLE buttons."""

from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.motionblinds_ble.const import (
    ATTR_CONNECT,
    ATTR_DISCONNECT,
    ATTR_FAVORITE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("button"),
    [
        ATTR_CONNECT,
        ATTR_DISCONNECT,
        ATTR_FAVORITE,
    ],
)
async def test_button(
    mock_config_entry: MockConfigEntry,
    mock_motion_device: Mock,
    name: str,
    hass: HomeAssistant,
    button: str,
) -> None:
    """Test states of the button."""

    await setup_integration(hass, mock_config_entry)

    command = AsyncMock()
    setattr(mock_motion_device, button, command)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: f"button.{name}_{button}"},
        blocking=True,
    )
    command.assert_called_once()
