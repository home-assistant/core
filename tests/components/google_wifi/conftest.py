"""Shared Google Wifi test helpers."""

from typing import Any

import aiohttp
import pytest

from .const import DEFAULT_RESPONSE, RESOURCE_URL

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def normal_response() -> dict[str, Any]:
    """Return a normal response from the API."""
    return DEFAULT_RESPONSE


@pytest.fixture
def mock_success(
    aioclient_mock: AiohttpClientMocker, normal_response: dict[str, Any]
) -> AiohttpClientMocker:
    """Mock a successful Google Wifi response."""
    aioclient_mock.get(RESOURCE_URL, json=normal_response)
    return aioclient_mock


@pytest.fixture
def mock_unreachable(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock an unreachable Google Wifi host."""
    aioclient_mock.get(
        RESOURCE_URL,
        exc=aiohttp.ClientConnectionError("connection refused"),
    )
    return aioclient_mock
