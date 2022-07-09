"""Discord notification test helpers."""
from http import HTTPStatus

import pytest

from homeassistant.components.discord.notify import DiscordNotificationService
from homeassistant.core import HomeAssistant

from tests.test_util.aiohttp import AiohttpClientMocker

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
def discord_aiohttp_mock_factory(
    aioclient_mock: AiohttpClientMocker,
) -> AiohttpClientMocker:
    """Create Discord service mock from factory."""

    def _discord_aiohttp_mock_factory(
        content_length_header: str = None,
    ) -> AiohttpClientMocker:
        if content_length_header is not None:
            aioclient_mock.get(
                URL_ATTACHMENT,
                status=HTTPStatus.OK,
                content=CONTENT,
                headers={"Content-Length": content_length_header},
            )
        else:
            aioclient_mock.get(
                URL_ATTACHMENT,
                status=HTTPStatus.OK,
                content=CONTENT,
            )
        return aioclient_mock

    return _discord_aiohttp_mock_factory
