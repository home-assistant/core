"""Test the Tessie button platform."""
from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_buttons(hass: HomeAssistant) -> None:
    """Tests that the button entities are correct."""

    await setup_platform(hass)

    # Test wake button
    with patch(
        "homeassistant.components.tessie.button.wake",
    ) as mock_wake:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ["button.test_wake"]},
            blocking=True,
        )
        mock_wake.assert_called_once()
