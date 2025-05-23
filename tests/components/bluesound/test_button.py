"""Test for bluesound buttons."""

from unittest.mock import call

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import PlayerMocks


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_sleep_timer(
    hass: HomeAssistant,
    player_mocks: PlayerMocks,
    setup_config_entry: None,
) -> None:
    """Test the media player volume set."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.player_name1111_set_sleep_timer"},
        blocking=True,
    )

    player_mocks.player_data.player.sleep_timer.assert_called_once()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_clear_sleep_timer(
    hass: HomeAssistant,
    player_mocks: PlayerMocks,
    setup_config_entry: None,
) -> None:
    """Test the media player volume set."""
    player_mocks.player_data.player.sleep_timer.side_effect = [15, 30, 45, 60, 90, 0]

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.player_name1111_clear_sleep_timer"},
        blocking=True,
    )

    player_mocks.player_data.player.sleep_timer.assert_has_calls([call()] * 6)
