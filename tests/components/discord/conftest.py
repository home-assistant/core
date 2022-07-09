"""Discord notification test helpers."""
from http import HTTPStatus

import pytest
from requests_mock.mocker import Mocker

from homeassistant.components.discord.notify import DiscordNotificationService
from homeassistant.core import HomeAssistant

MESSAGE = "Testing Discord Messenger platform"
CONTENT = b"TestContent"
URL_ATTACHMENT = "http://127.0.0.1:8080/image.jpg"
TARGET = "1234567890"


@pytest.fixture
def discord_notification_service(hass: HomeAssistant) -> DiscordNotificationService:
    """Set up discord notification service."""
    hass.config.allowlist_external_urls.add(URL_ATTACHMENT)
    token = "token"
    return DiscordNotificationService(hass, token)


@pytest.fixture
def discord_requests_mock_factory(requests_mock: Mocker) -> Mocker:
    """Create Discord service mock from factory."""

    def _discord_requests_mock_factory(content_length_header: str = None) -> Mocker:
        if content_length_header is not None:
            requests_mock.register_uri(
                "GET",
                URL_ATTACHMENT,
                status_code=HTTPStatus.OK,
                content=CONTENT,
                headers={"Content-Length": content_length_header},
            )
        else:
            requests_mock.register_uri(
                "GET",
                URL_ATTACHMENT,
                status_code=HTTPStatus.OK,
                content=CONTENT,
            )
        return requests_mock

    return _discord_requests_mock_factory
