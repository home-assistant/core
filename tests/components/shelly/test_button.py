"""Tests for Shelly button platform."""
from __future__ import annotations

from spencerassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from spencerassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from spencerassistant.core import spencerAssistant

from . import init_integration


async def test_block_button(hass: spencerAssistant, mock_block_device):
    """Test block device reboot button."""
    await init_integration(hass, 1)

    # reboot button
    assert hass.states.get("button.test_name_reboot").state == STATE_UNKNOWN

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_name_reboot"},
        blocking=True,
    )
    assert mock_block_device.trigger_reboot.call_count == 1


async def test_rpc_button(hass: spencerAssistant, mock_rpc_device):
    """Test rpc device OTA button."""
    await init_integration(hass, 2)

    # reboot button
    assert hass.states.get("button.test_name_reboot").state == STATE_UNKNOWN

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_name_reboot"},
        blocking=True,
    )
    assert mock_rpc_device.trigger_reboot.call_count == 1
