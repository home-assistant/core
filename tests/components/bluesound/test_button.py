"""Test for bluesound buttons."""

from unittest.mock import call

from pyblu.errors import (
    PlayerError,
    PlayerUnexpectedResponseError,
    PlayerUnreachableError,
)
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_config_entry")
@pytest.mark.parametrize(
    "entity_id",
    [
        "button.player_name1111_set_sleep_timer",
        "button.player_name1111_clear_sleep_timer",
    ],
)
@pytest.mark.parametrize(
    ("error", "message"),
    [
        pytest.param(
            PlayerUnreachableError("timeout"),
            "Could not reach the Bluesound player: timeout",
            id="unreachable",
        ),
        pytest.param(
            PlayerUnexpectedResponseError("bad xml"),
            "The Bluesound player returned an unexpected response: bad xml",
            id="unexpected_response",
        ),
    ],
)
async def test_press_error(
    hass: HomeAssistant,
    player_mocks: PlayerMocks,
    entity_id: str,
    error: PlayerError,
    message: str,
) -> None:
    """Test that a failing button press raises HomeAssistantError."""
    player_mocks.player_data.player.sleep_timer.side_effect = error

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
