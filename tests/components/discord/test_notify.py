"""Test Discord notify."""

import logging

import pytest

from homeassistant.components.discord.notify import DiscordNotificationService

from .conftest import CONTENT, MESSAGE, URL_ATTACHMENT

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
    """Test getting file from URL with large attachment (per Content-Length header) throws error."""
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
    """Test getting file from URL with large attachment (per content length) throws error."""
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
