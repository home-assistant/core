"""Test the Discord notify entity."""

from unittest.mock import AsyncMock, MagicMock

import nextcord
import pytest

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import CHANNEL_NAME

# The entity_id is generated from the bot title + channel name.
# With has_entity_name=True: "Mock Discord Bot General"  → notify.mock_discord_bot_general
ENTITY_ID = f"notify.mock_discord_bot_{CHANNEL_NAME}"


async def test_send_message(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test sending a basic text message to a Discord channel."""
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MESSAGE: "Hello Discord!",
        },
        blocking=True,
    )

    mock_channel.send.assert_called_once_with("Hello Discord!")


async def test_send_message_with_title(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test that a title is prepended in bold to the message."""
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_MESSAGE: "Hello",
            ATTR_TITLE: "Alert",
        },
        blocking=True,
    )

    mock_channel.send.assert_called_once_with("**Alert**\nHello")


async def test_send_message_channel_not_found(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
) -> None:
    """Test that a HomeAssistantError is raised when the channel is not found."""
    mock_discord_bot.fetch_channel = AsyncMock(
        side_effect=nextcord.NotFound(MagicMock(), "")
    )
    mock_discord_bot.fetch_user = AsyncMock(
        side_effect=nextcord.NotFound(MagicMock(), "")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MESSAGE: "test"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "channel_not_found"


async def test_send_message_falls_back_to_dm(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test that an unknown channel ID falls back to a DM user lookup."""
    mock_discord_bot.fetch_channel = AsyncMock(
        side_effect=nextcord.NotFound(MagicMock(), "")
    )
    mock_discord_bot.fetch_user = AsyncMock(return_value=mock_channel)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MESSAGE: "DM!"},
        blocking=True,
    )

    mock_channel.send.assert_called_once()


async def test_send_message_http_error_raises(
    hass: HomeAssistant,
    setup_discord: None,
    mock_discord_bot: MagicMock,
    mock_channel: MagicMock,
) -> None:
    """Test that an HTTP error during send raises HomeAssistantError."""
    mock_channel.send = AsyncMock(
        side_effect=nextcord.HTTPException(MagicMock(), "rate limited")
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MESSAGE: "oops"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "send_message_failed"
