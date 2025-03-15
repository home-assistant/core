"""Tests for the squeezebox button component."""

from unittest.mock import MagicMock

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant


async def test_squeezebox_press(
    hass: HomeAssistant, configured_player_with_button: MagicMock
) -> None:
    """Test turn on service call."""
    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: "button.test_player_preset_1"},
        blocking=True,
    )

    configured_player_with_button.async_query.assert_called_with(
        "button", "preset_1.single"
    )
