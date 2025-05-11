"""Common fixtures for the Model Context Protocol tests."""

from collections.abc import Generator
import datetime
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.mcp.const import (
    CONF_ACCESS_TOKEN,
    CONF_AUTHORIZATION_URL,
    CONF_TOKEN_URL,
    DOMAIN,
)
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TEST_API_NAME = "Memory Server"
MCP_SERVER_URL = "http://1.1.1.1:8080/sse"
CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-client-secret"
AUTH_DOMAIN = "some-auth-domain"
OAUTH_AUTHORIZE_URL = "https://example-auth-server.com/authorize-path"
OAUTH_TOKEN_URL = "https://example-auth-server.com/token-path"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.mcp.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_mcp_client() -> Generator[AsyncMock]:
    """Fixture to mock the MCP client."""
    with (
        patch("homeassistant.components.mcp.coordinator.sse_client"),
        patch("homeassistant.components.mcp.coordinator.ClientSession") as mock_session,
        patch("homeassistant.components.mcp.coordinator.TIMEOUT", 1),
    ):
        yield mock_session.return_value.__aenter__


@pytest.fixture(name="config_entry")
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Fixture to load the integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://1.1.1.1/sse"},
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(name="credential")
async def mock_credential(hass: HomeAssistant) -> None:
    """Fixture that provides the ClientCredential for the test."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        AUTH_DOMAIN,
    )


@pytest.fixture(name="config_entry_token_expiration")
def mock_config_entry_token_expiration() -> datetime.datetime:
    """Fixture to mock the token expiration."""
    return datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)


@pytest.fixture(name="config_entry_with_auth")
def mock_config_entry_with_auth(
    hass: HomeAssistant,
    config_entry_token_expiration: datetime.datetime,
) -> MockConfigEntry:
    """Fixture to load the integration with authentication."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=AUTH_DOMAIN,
        data={
            "auth_implementation": AUTH_DOMAIN,
            CONF_URL: MCP_SERVER_URL,
            CONF_AUTHORIZATION_URL: OAUTH_AUTHORIZE_URL,
            CONF_TOKEN_URL: OAUTH_TOKEN_URL,
            CONF_TOKEN: {
                CONF_ACCESS_TOKEN: "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": config_entry_token_expiration.timestamp(),
            },
        },
        title=TEST_API_NAME,
    )
    config_entry.add_to_hass(hass)
    return config_entry
