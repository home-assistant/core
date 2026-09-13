"""The tests for the Rfxtrx services."""

import pytest
import voluptuous as vol

from homeassistant.components.rfxtrx import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component


async def test_send_invalid_event(hass: HomeAssistant) -> None:
    """Test send of an invalid event fails validation."""
    await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, "send", {"event": "invalid"}, blocking=True
        )


async def test_send_not_connected(hass: HomeAssistant) -> None:
    """Test send fails if there is no active RFXtrx connection."""
    await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(HomeAssistantError, match="RFXtrx is not connected"):
        await hass.services.async_call(
            DOMAIN, "send", {"event": "0a520802060101ff0f0269"}, blocking=True
        )
