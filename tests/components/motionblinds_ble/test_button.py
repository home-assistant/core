"""Tests for Motionblinds BLE buttons."""

import logging
from unittest.mock import patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.motionblinds_ble.const import (
    ATTR_CONNECT,
    ATTR_DISCONNECT,
    ATTR_FAVORITE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from . import setup_platform

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(("button"), [ATTR_CONNECT, ATTR_DISCONNECT, ATTR_FAVORITE])
async def test_button(hass: HomeAssistant, button: str) -> None:
    """Test states of the button."""

    _, name = await setup_platform(hass, [Platform.BUTTON])

    with patch(
        f"homeassistant.components.motionblinds_ble.MotionDevice.{button}"
    ) as command:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: f"button.{name}_{button}"},
            blocking=True,
        )
        command.assert_called_once()

    await hass.async_block_till_done()
