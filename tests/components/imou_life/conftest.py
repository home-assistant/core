from collections.abc import Generator
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from pyimouapi import ImouOpenApiClient, InvalidAppIdOrSecretException

IMOU_TOKEN_RETURN = {
    "accessToken": "test_token",
    "expireTime": 3600,
    "currentDomain": "https://openapi.imoulife.com:443",
}


@pytest.fixture
def imou_config_flow() -> Generator[MagicMock]:
    with (
        patch.object(ImouOpenApiClient, "async_get_token", return_value=True),
        patch(
            "homeassistant.components.imou_life.config_flow.ImouOpenApiClient"
        ) as mock_client,
    ):
        instance = mock_client.return_value = ImouOpenApiClient(
            "test_app_id", "test_app_secret", "openapi.imoulife.com"
        )
        instance.async_get_token = AsyncMock(return_value=IMOU_TOKEN_RETURN)
        yield mock_client


@pytest.fixture
def imou_config_flow_exception() -> Generator[MagicMock]:
    with (
        patch.object(ImouOpenApiClient, "async_get_token", return_value=True),
        patch(
            "homeassistant.components.imou_life.config_flow.ImouOpenApiClient"
        ) as mock_client,
    ):
        instance = mock_client.return_value = ImouOpenApiClient(
            "test_app_id", "test_app_secret", "openapi.imoulife.com"
        )
        instance.async_get_token = AsyncMock(
            side_effect=InvalidAppIdOrSecretException()
        )
        yield mock_client
