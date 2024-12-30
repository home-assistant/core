"""Config for the Imou camera integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyimouapi import ImouOpenApiClient, InvalidAppIdOrSecretException
import pytest

IMOU_TOKEN_RETURN = {
    "accessToken": "test_token",
    "expireTime": 3600,
    "currentDomain": "https://openapi.imoulife.com:443",
}


@pytest.fixture
def imou_config_flow() -> Generator[MagicMock]:
    """Fixture to mock the Imou Open API Client for testing configuration flows.

    Yields:
       MagicMock: A mocked instance of ImouOpenApiClient.

    """
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
    """Create a test fixture that simulates the behavior of the Imou Open API client.

    This test fixture is used to simulate exceptions that may be raised by the Imou Open API client during the configuration flow.
    It uses the `patch` decorator to replace the behavior of the `ImouOpenApiClient` class, allowing a mocked instance to be used in tests.

    Returns:
        Generator[MagicMock]: A generated mocked client instance that raises an exception when `async_get_token` is called.

    """
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
