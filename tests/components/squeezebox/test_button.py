"""Tests for the squeezebox button component."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.squeezebox.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_MAC


@pytest.fixture(autouse=True)
def squeezebox_button_platform():
    """Only set up the media_player platform for squeezebox tests."""
    with patch("homeassistant.components.squeezebox.PLATFORMS", [Platform.BUTTON]):
        yield


async def test_squeezebox_press(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    configured_player: MagicMock,
) -> None:
    """Test press service call."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.BUTTON, DOMAIN, f"{TEST_MAC[0]}_preset_1"
    )
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    configured_player.async_query.assert_called_with("button", "preset_1.single")
