"""Test Snoo Buttons."""

from unittest.mock import AsyncMock

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import async_init_integration


async def test_button_starts_snoo(hass: HomeAssistant, bypass_api: AsyncMock) -> None:
    """Test start_snoo button works correctly."""
    await async_init_integration(hass)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_snoo_start"},
        blocking=True,
    )

    assert bypass_api.start_snoo.assert_called_once
