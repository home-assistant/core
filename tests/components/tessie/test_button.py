"""Test the Tessie button platform."""

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.tessie.button import DESCRIPTIONS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import patch_description, setup_platform


async def test_buttons(hass: HomeAssistant) -> None:
    """Tests that the button entities are correct."""

    await setup_platform(hass)

    # Test wake button
    with patch_description(DESCRIPTIONS, "wake", "func") as mock_wake:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ["button.test_wake"]},
            blocking=True,
        )
        mock_wake.assert_called_once()
