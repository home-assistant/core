"""Test Discord notify."""

import logging
from unittest.mock import AsyncMock, Mock, patch

import nextcord
import pytest

from homeassistant.components.discord.notify import DiscordNotificationService
from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import TARGET_NAME, create_entry, setup_integration
from .conftest import CONTENT, MESSAGE, TARGET, URL_ATTACHMENT

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_send_message_without_target_logs_error(
    discord_notification_service: DiscordNotificationService,
    discord_aiohttp_mock_factory: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test send message."""
    discord_aiohttp_mock = discord_aiohttp_mock_factory()
    with caplog.at_level(
        logging.ERROR, logger="homeassistant.components.discord.notify"
    ):
        await discord_notification_service.async_send_message(MESSAGE)
    assert "No target specified" in caplog.text
    assert discord_aiohttp_mock.call_count == 0


async def test_get_file_from_url(
    discord_notification_service: DiscordNotificationService,
    discord_aiohttp_mock_factory: AiohttpClientMocker,
) -> None:
    """Test getting a file from a URL."""
    headers = {"Content-Length": str(len(CONTENT))}
    discord_aiohttp_mock = discord_aiohttp_mock_factory(headers)
    result = await discord_notification_service.async_get_file_from_url(
        URL_ATTACHMENT, True, len(CONTENT)
    )

    assert discord_aiohttp_mock.call_count == 1
    assert result == bytearray(CONTENT)


async def test_get_file_from_url_not_on_allowlist(
    discord_notification_service: DiscordNotificationService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test getting file from URL that isn't on the allowlist."""
    url = "http://dodgyurl.com"
    with caplog.at_level(
        logging.WARNING, logger="homeassistant.components.discord.notify"
    ):
        result = await discord_notification_service.async_get_file_from_url(
            url, True, len(CONTENT)
        )

    assert f"URL not allowed: {url}" in caplog.text
    assert result is None


async def test_get_file_from_url_with_large_attachment(
    discord_notification_service: DiscordNotificationService,
    discord_aiohttp_mock_factory: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test getting file from URL with large attachment throws error."""
    headers = {"Content-Length": str(len(CONTENT) + 1)}
    discord_aiohttp_mock = discord_aiohttp_mock_factory(headers)
    with caplog.at_level(
        logging.WARNING, logger="homeassistant.components.discord.notify"
    ):
        result = await discord_notification_service.async_get_file_from_url(
            URL_ATTACHMENT, True, len(CONTENT)
        )

    assert discord_aiohttp_mock.call_count == 1
    assert "Attachment too large (Content-Length reports" in caplog.text
    assert result is None


async def test_get_file_from_url_with_large_attachment_no_header(
    discord_notification_service: DiscordNotificationService,
    discord_aiohttp_mock_factory: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test getting file from URL with large attachment without header throws error."""
    discord_aiohttp_mock = discord_aiohttp_mock_factory()
    with caplog.at_level(
        logging.WARNING, logger="homeassistant.components.discord.notify"
    ):
        result = await discord_notification_service.async_get_file_from_url(
            URL_ATTACHMENT, True, len(CONTENT) - 1
        )

    assert discord_aiohttp_mock.call_count == 1
    assert "Attachment too large (Stream reports" in caplog.text
    assert result is None


async def test_notify_entity_send_message(hass: HomeAssistant) -> None:
    """Test sending a message through the notify entity."""
    entry = create_entry(hass, with_subentry=True)
    await setup_integration(hass, entry)

    channel = Mock()
    channel.send = AsyncMock()

    with (
        patch("homeassistant.components.discord.notify.nextcord.Client.login"),
        patch(
            "homeassistant.components.discord.notify.nextcord.Client.fetch_channel",
            new=AsyncMock(return_value=channel),
        ),
        patch("homeassistant.components.discord.notify.nextcord.Client.close"),
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_ENTITY_ID: f"notify.{TARGET_NAME}", "message": MESSAGE},
            blocking=True,
        )

    channel.send.assert_awaited_once_with(MESSAGE)


async def test_notify_entity_target_not_found(hass: HomeAssistant) -> None:
    """Test the notify entity raises an error for an unknown target."""
    entry = create_entry(hass, with_subentry=True)
    await setup_integration(hass, entry)

    not_found = nextcord.NotFound(Mock(status=404), "")

    with (
        patch("homeassistant.components.discord.notify.nextcord.Client.login"),
        patch(
            "homeassistant.components.discord.notify.nextcord.Client.fetch_channel",
            new=AsyncMock(side_effect=not_found),
        ),
        patch(
            "homeassistant.components.discord.notify.nextcord.Client.fetch_user",
            new=AsyncMock(side_effect=not_found),
        ),
        patch("homeassistant.components.discord.notify.nextcord.Client.close"),
        pytest.raises(HomeAssistantError, match=f"Target not found for ID: {TARGET}"),
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_ENTITY_ID: f"notify.{TARGET_NAME}", "message": MESSAGE},
            blocking=True,
        )


async def test_notify_entity_communication_error(hass: HomeAssistant) -> None:
    """Test the notify entity raises an error when sending fails."""
    entry = create_entry(hass, with_subentry=True)
    await setup_integration(hass, entry)

    channel = Mock()
    channel.send = AsyncMock(side_effect=nextcord.HTTPException(Mock(status=400), ""))

    with (
        patch("homeassistant.components.discord.notify.nextcord.Client.login"),
        patch(
            "homeassistant.components.discord.notify.nextcord.Client.fetch_channel",
            new=AsyncMock(return_value=channel),
        ),
        patch("homeassistant.components.discord.notify.nextcord.Client.close"),
        pytest.raises(HomeAssistantError, match="Error sending message to Discord"),
    ):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {ATTR_ENTITY_ID: f"notify.{TARGET_NAME}", "message": MESSAGE},
            blocking=True,
        )
