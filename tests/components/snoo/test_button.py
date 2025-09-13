"""Test Snoo Buttons."""

import copy
from unittest.mock import AsyncMock

from python_snoo.containers import SnooDevice

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import async_init_integration, find_update_callback
from .const import MOCK_SNOO_DATA


async def test_button_starts_snoo(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test start_snoo button works correctly."""
    await async_init_integration(hass)

    async def start_snoo(device: SnooDevice):
        new_data = copy.deepcopy(MOCK_SNOO_DATA)
        new_data.state_machine.state = "BASELINE"
        find_update_callback(bypass_api, device.serialNumber)(new_data)

    bypass_api.start_snoo.side_effect = start_snoo
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_snoo_start"},
        blocking=True,
    )

    assert bypass_api.start_snoo.assert_called_once
