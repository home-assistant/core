"""Tests for the squeezebox button component."""

from unittest.mock import MagicMock

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def test_squeezebox_press(
    hass: HomeAssistant, configured_player_with_button: MagicMock
) -> None:
    """Test press service call."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_player_preset_1"},
        blocking=True,
    )

    configured_player_with_button.async_query.assert_called_with(
        "button", "preset_1.single"
    )
