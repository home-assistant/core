"""Fixtures for the Beatbot integration tests."""

from collections.abc import Generator
import time
from unittest.mock import AsyncMock, MagicMock, patch

from beatbot_cloud.const import OAUTH2_CLIENT_ID
import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.beatbot.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import batch_state, create_device, setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def mock_http_session(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Replace the shared client session before the integration can create one.

    Beatbot builds its client session while setting up, so the mock has to be
    active from the start or a later HTTP call would escape to the network.
    """
    return aioclient_mock


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Register the Beatbot OAuth implementation."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(OAUTH2_CLIENT_ID, ""), DOMAIN
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Beatbot config entry holding a valid token."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Beatbot",
        unique_id="account-1",
        data={
            "auth_implementation": DOMAIN,
            "region": "cn",
            "token": {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "token_type": "bearer",
                "expires_at": time.time() + 3600,
            },
        },
    )


@pytest.fixture
def mock_client_class() -> Generator[MagicMock]:
    """Mock the library REST client class for the integration and the config flow."""
    with (
        patch(
            "homeassistant.components.beatbot.BeatbotClient", autospec=True
        ) as client_mock,
        patch(
            "homeassistant.components.beatbot.config_flow.BeatbotClient",
            new=client_mock,
        ),
    ):
        yield client_mock


@pytest.fixture
def mock_client(mock_client_class: MagicMock) -> MagicMock:
    """Mock the library REST client with one online pool cleaner."""
    client = mock_client_class.return_value
    client.get_devices.return_value = [create_device()]
    client.get_device_states.return_value = batch_state()
    return client


@pytest.fixture
def mock_event_client() -> Generator[MagicMock]:
    """Mock the library event client.

    The integration builds its own event client wrapper, so only the library
    class it hands the callbacks to is replaced. Yielding the class mock lets
    tests reach those callbacks through `library_callback`.
    """
    with patch(
        "homeassistant.components.beatbot.event_stream.BeatbotCloudEventClient"
    ) as event_client_cls:
        event_client_cls.return_value.async_run = AsyncMock()
        event_client_cls.return_value.async_close = AsyncMock()
        yield event_client_cls


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    mock_event_client: MagicMock,
) -> MockConfigEntry:
    """Set up the Beatbot integration."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config-flow tests from setting up the integration."""
    with patch(
        "homeassistant.components.beatbot.async_setup_entry", return_value=True
    ) as setup_entry:
        yield setup_entry
