"""Tests for rainbird initialization."""

from http import HTTPStatus

from homeassistant.core import HomeAssistant

from .conftest import URL, ComponentSetup

from tests.test_util.aiohttp import AiohttpClientMocker, AiohttpClientMockResponse


async def test_setup_success(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test successful setup and unload."""

    assert await setup_integration()


async def test_setup_communication_failure(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    responses: list[AiohttpClientMockResponse],
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test unable to talk to server on startup, which permanently fails setup."""

    responses.clear()
    responses.append(
        AiohttpClientMockResponse("POST", URL, status=HTTPStatus.SERVICE_UNAVAILABLE)
    )

    assert not await setup_integration()
