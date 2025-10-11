"""Tests for the squeezebox button component."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def squeezebox_button_platform():
    """Only set up the media_player platform for squeezebox tests."""
    with patch("homeassistant.components.squeezebox.PLATFORMS", [Platform.BUTTON]):
        yield


async def test_squeezebox_press(
    hass: HomeAssistant, configured_player: MagicMock
) -> None:
    """Test press service call."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.none_preset_1"},
        blocking=True,
    )

    configured_player.async_query.assert_called_with("button", "preset_1.single")
