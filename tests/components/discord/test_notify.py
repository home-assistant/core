"""Test Discord notify."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import nextcord
import pytest

from homeassistant.components.discord.notify import DiscordNotificationService
from homeassistant.components.notify import ATTR_TARGET
from homeassistant.exceptions import HomeAssistantError

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


async def test_send_message_communication_error(
    discord_notification_service: DiscordNotificationService,
) -> None:
    """Test send message raises on a Discord communication error."""
    client = MagicMock()
    client.login = AsyncMock()
    client.close = AsyncMock()
    client.fetch_channel = AsyncMock(
        side_effect=nextcord.HTTPException(
            MagicMock(status=500, reason="Server Error"), "error"
        )
    )
    with (
        patch(
            "homeassistant.components.discord.notify.nextcord.Client",
            return_value=client,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await discord_notification_service.async_send_message(
            MESSAGE, **{ATTR_TARGET: [TARGET]}
        )
    assert exc_info.value.translation_key == "communication_error"
    client.close.assert_awaited_once()


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
