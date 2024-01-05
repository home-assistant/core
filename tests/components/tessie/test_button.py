"""Test the Tessie button platform."""
from unittest.mock import patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import setup_platform


@pytest.mark.parametrize(
    ("entity_id", "func"),
    [
        ("button.test_wake", "wake"),
        ("button.test_flash_lights", "flash_lights"),
        ("button.test_honk_horn", "honk"),
        ("button.test_homelink", "trigger_homelink"),
        ("button.test_keyless_driving", "enable_keyless_driving"),
        ("button.test_play_fart", "boombox"),
    ],
)
async def test_buttons(hass: HomeAssistant, entity_id, func) -> None:
    """Tests that the button entities are correct."""

    await setup_platform(hass)

    # Test wake button
    with patch(
        f"homeassistant.components.tessie.button.{func}",
    ) as mock_wake:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_wake.assert_called_once()
