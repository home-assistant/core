"""Test Discord notify."""
import logging

import pytest
from requests_mock.mocker import Mocker

from homeassistant.components.discord.notify import DiscordNotificationService

from .conftest import CONTENT, MESSAGE, URL_ATTACHMENT


async def test_send_message_without_target_logs_error(
    discord_notification_service: DiscordNotificationService,
    discord_requests_mock_factory: Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test send message."""
    discord_requests_mock = discord_requests_mock_factory()
    with caplog.at_level(
        logging.ERROR, logger="homeassistant.components.discord.notify"
    ):
        await discord_notification_service.async_send_message(MESSAGE)
    assert "No target specified" in caplog.text
    assert not discord_requests_mock.called


def test_get_file_from_url_with_true_verify(
    discord_notification_service: DiscordNotificationService,
    discord_requests_mock_factory: Mocker,
) -> None:
    """Test getting a file from a URL."""
    discord_requests_mock = discord_requests_mock_factory(str(len(CONTENT)))
    result = discord_notification_service.get_file_from_url(
        URL_ATTACHMENT, True, len(CONTENT)
    )

    assert discord_requests_mock.called
    assert discord_requests_mock.call_count == 1
    assert discord_requests_mock.last_request.verify is True
    assert result == bytearray(CONTENT)


def test_get_file_from_url_with_false_verify(
    discord_notification_service: DiscordNotificationService,
    discord_requests_mock_factory: Mocker,
) -> None:
    """Test getting a file from a URL."""
    discord_requests_mock = discord_requests_mock_factory(str(len(CONTENT)))
    result = discord_notification_service.get_file_from_url(
        URL_ATTACHMENT, False, len(CONTENT)
    )

    assert discord_requests_mock.called
    assert discord_requests_mock.call_count == 1
    assert discord_requests_mock.last_request.verify is False
    assert result == bytearray(CONTENT)


def test_get_file_from_url_not_on_allowlist(
    discord_notification_service: DiscordNotificationService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test getting file from URL that isn't on the allowlist."""
    url = "http://dodgyurl.com"
    with caplog.at_level(
        logging.WARNING, logger="homeassistant.components.discord.notify"
    ):
        result = discord_notification_service.get_file_from_url(url, True, len(CONTENT))

    assert f"URL not allowed: {url}" in caplog.text
    assert result is None


def test_get_file_from_url_with_large_attachment(
    discord_notification_service: DiscordNotificationService,
    discord_requests_mock_factory: Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test getting file from URL with large attachment (per Content-Length header) throws error."""
    discord_requests_mock = discord_requests_mock_factory(str(len(CONTENT) + 1))
    with caplog.at_level(
        logging.WARNING, logger="homeassistant.components.discord.notify"
    ):
        result = discord_notification_service.get_file_from_url(
            URL_ATTACHMENT, True, len(CONTENT)
        )

    assert discord_requests_mock.called
    assert discord_requests_mock.call_count == 1
    assert "Attachment too large (Content-Length reports" in caplog.text
    assert result is None


def test_get_file_from_url_with_large_attachment_no_header(
    discord_notification_service: DiscordNotificationService,
    discord_requests_mock_factory: Mocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test getting file from URL with large attachment (per content length) throws error."""
    discord_requests_mock = discord_requests_mock_factory()
    with caplog.at_level(
        logging.WARNING, logger="homeassistant.components.discord.notify"
    ):
        result = discord_notification_service.get_file_from_url(
            URL_ATTACHMENT, True, len(CONTENT) - 1
        )

    assert discord_requests_mock.called
    assert discord_requests_mock.call_count == 1
    assert "Attachment too large (Stream reports" in caplog.text
    assert result is None
