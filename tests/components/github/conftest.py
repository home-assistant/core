"""conftest for the GitHub integration."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aiogithubapi import (
    GitHubLoginDeviceModel,
    GitHubLoginOauthModel,
    GitHubRateLimitModel,
)
import pytest

from homeassistant.components.github.const import CONF_REPOSITORIES, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from .const import MOCK_ACCESS_TOKEN, TEST_REPOSITORY

from tests.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    load_json_object_fixture,
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN},
        options={CONF_REPOSITORIES: [TEST_REPOSITORY]},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.github.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def device_activation_event() -> asyncio.Event:
    """Fixture to provide an asyncio event for device activation."""
    return asyncio.Event()


@pytest.fixture
def github_device_client(
    hass: HomeAssistant,
    device_activation_event: asyncio.Event,
) -> Generator[AsyncMock]:
    """Mock GitHub device client."""
    with patch(
        "homeassistant.components.github.config_flow.GitHubDeviceAPI",
        autospec=True,
    ) as github_client_mock:
        client = github_client_mock.return_value
        register_object = AsyncMock()
        register_object.data = GitHubLoginDeviceModel(
            load_json_object_fixture("device_register.json", DOMAIN)
        )
        client.register.return_value = register_object

        async def mock_api_device_activation(device_code) -> AsyncMock:
            # Simulate the device activation process
            await device_activation_event.wait()
            activate_object = AsyncMock()
            activate_object.data = GitHubLoginOauthModel(
                await async_load_json_object_fixture(
                    hass, "device_activate.json", DOMAIN
                )
            )
            return activate_object

        client.activation = mock_api_device_activation
        yield client


@pytest.fixture
def github_client(hass: HomeAssistant) -> Generator[AsyncMock]:
    """Mock GitHub device client."""
    with (
        patch(
            "homeassistant.components.github.config_flow.GitHubAPI",
            autospec=True,
        ) as github_client_mock,
        patch("homeassistant.components.github.GitHubAPI", new=github_client_mock),
        patch(
            "homeassistant.components.github.diagnostics.GitHubAPI",
            new=github_client_mock,
        ),
    ):
        client = github_client_mock.return_value
        client.user.starred = AsyncMock(
            side_effect=[
                MagicMock(
                    is_last_page=False,
                    next_page_number=2,
                    last_page_number=2,
                    data=[MagicMock(full_name="home-assistant/core")],
                ),
                MagicMock(
                    is_last_page=True,
                    data=[MagicMock(full_name="home-assistant/frontend")],
                ),
            ]
        )
        client.user.repos = AsyncMock(
            side_effect=[
                MagicMock(
                    is_last_page=False,
                    next_page_number=2,
                    last_page_number=2,
                    data=[MagicMock(full_name="home-assistant/operating-system")],
                ),
                MagicMock(
                    is_last_page=True,
                    data=[MagicMock(full_name="esphome/esphome")],
                ),
            ]
        )
        rate_limit_mock = AsyncMock()
        rate_limit_mock.data = GitHubRateLimitModel(
            load_json_object_fixture("rate_limit.json", DOMAIN)
        )
        client.rate_limit.return_value = rate_limit_mock
        graphql_mock = AsyncMock()
        graphql_mock.data = load_json_object_fixture("graphql.json", DOMAIN)
        client.graphql.return_value = graphql_mock
        client.repos.events.subscribe = AsyncMock()
        yield client
