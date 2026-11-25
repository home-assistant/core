"""Shared Google Wifi test helpers."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.google_wifi import CONF_HOST, DOMAIN
from homeassistant.core import HomeAssistant

from .const import DEFAULT_RESPONSE, RESOURCE_URL


def _resource_url_for_host(host: str) -> str:
    """Return the resource URL for a given host."""
    return f"http://{host}/api/v1/status"


@pytest.fixture
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a Google Wifi config entry."""
    return MockConfigEntry(
        domain=DOMAIN, title="Google Wifi", data={CONF_HOST: "192.168.86.1"}
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.google_wifi.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def normal_response() -> dict[str, Any]:
    """Return a normal response from the API."""
    return DEFAULT_RESPONSE


@pytest.fixture
def device_response(request: pytest.FixtureRequest) -> dict[str, Any]:
    """Return a parametrized device response from the API."""
    return request.param


@pytest.fixture
def mock_success(
    aioclient_mock: AiohttpClientMocker, normal_response: dict[str, Any]
) -> AiohttpClientMocker:
    """Mock a successful Google Wifi response."""
    aioclient_mock.get(RESOURCE_URL, json=normal_response)
    return aioclient_mock


@pytest.fixture
def mock_device_response(
    aioclient_mock: AiohttpClientMocker, device_response: dict[str, Any]
) -> AiohttpClientMocker:
    """Mock a Google Wifi response for a different device."""
    aioclient_mock.get(RESOURCE_URL, json=device_response)
    return aioclient_mock


@pytest.fixture
def mock_device_response_with_optional_error(
    aioclient_mock: AiohttpClientMocker,
    request: pytest.FixtureRequest,
) -> AiohttpClientMocker:
    """Mock a Google Wifi response for a different device with an optional error.

    Parametrize with a dict: {"host": str, "response": dict, "error": Exception | None}.
    Defaults to {"host": "192.168.86.1", "response": DEFAULT_RESPONSE, "error": None}.
    """
    resource = _resource_url_for_host(request.param.get("host", "192.168.86.1"))
    if error := request.param.get("error"):
        aioclient_mock.get(resource, exc=error)
    else:
        aioclient_mock.get(
            resource, json=request.param.get("response", DEFAULT_RESPONSE)
        )
    return aioclient_mock


@pytest.fixture
def mock_unreachable(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock an unreachable Google Wifi host."""
    aioclient_mock.get(
        RESOURCE_URL,
        exc=aiohttp.ClientConnectionError("connection refused"),
    )
    return aioclient_mock
