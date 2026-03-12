"""Shared fixtures for Dropbox integration tests."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.dropbox.const import DOMAIN, OAUTH2_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
ACCOUNT_ID = "dbid:1234567890abcdef"
ACCOUNT_EMAIL = "user@example.com"
CONFIG_ENTRY_TITLE = "Dropbox test account"
TEST_AGENT_ID = f"{DOMAIN}.{ACCOUNT_ID}"


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Set up application credentials for Dropbox."""

    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture
def account_info() -> SimpleNamespace:
    """Return mocked Dropbox account information."""

    return SimpleNamespace(account_id=ACCOUNT_ID, email=ACCOUNT_EMAIL)


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a default Dropbox config entry."""

    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=ACCOUNT_ID,
        title=CONFIG_ENTRY_TITLE,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": 1_725_000_000,
                "scope": " ".join(OAUTH2_SCOPES),
            },
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""

    with patch(
        "homeassistant.components.dropbox.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_dropbox_client(account_info: SimpleNamespace) -> Generator[MagicMock]:
    """Patch DropboxAPIClient instances used by the integration."""

    client = MagicMock()
    client.get_account_info = AsyncMock(return_value=account_info)
    client.list_folder = AsyncMock(return_value=[])
    client.download_file = MagicMock()
    client.upload_file = AsyncMock()
    client.delete_file = AsyncMock()

    with (
        patch(
            "homeassistant.components.dropbox.config_flow.DropboxAPIClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.dropbox.DropboxAPIClient",
            return_value=client,
        ),
    ):
        yield client
