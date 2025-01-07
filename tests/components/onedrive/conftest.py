"""Fixtures for OneDrive tests."""

from collections.abc import Generator
import time
from unittest.mock import AsyncMock, MagicMock, patch

from msgraph.generated.models.drive import Drive
from msgraph.generated.models.drive_item import DriveItem
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.onedrive.const import (
    CONF_APPROOT_ID,
    DOMAIN,
    OAUTH_SCOPES,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import CLIENT_ID, CLIENT_SECRET

from tests.common import MockConfigEntry


@pytest.fixture(name="scopes")
def mock_scopes() -> list[str]:
    """Fixture to set the scopes present in the OAuth token."""
    return OAUTH_SCOPES


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        DOMAIN,
    )


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def mock_config_entry(
    expires_at: int, scopes: list[str], mock_drive: Drive
) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=DOMAIN,
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": " ".join(scopes),
            },
            CONF_APPROOT_ID: "approot",
        },
        unique_id=mock_drive.id,
    )


@pytest.fixture
def mock_drive() -> Generator[Drive]:
    """Return a mocked Drive."""
    drive = Drive()
    drive.id = "mock_drive_id"
    return drive


@pytest.fixture
def mock_graph_client(mock_drive: Drive) -> Generator[MagicMock]:
    """Return a mocked GraphServiceClient."""
    with (
        patch(
            "homeassistant.components.onedrive.config_flow.GraphServiceClient",
            autospec=True,
        ) as graph_client,
        patch(
            "homeassistant.components.onedrive.GraphServiceClient",
            new=graph_client,
        ),
    ):
        client = graph_client.return_value
        client.me.drive.get = AsyncMock(return_value=mock_drive)

        client.drives.by_drive_id.return_value.special.by_drive_item_id.return_value.get = AsyncMock(
            return_value=DriveItem(id="approot")
        )
        client.drives.by_drive_id.return_value.items.by_drive_item_id.return_value.get = AsyncMock(
            return_value=DriveItem(id="folder_id")
        )

        client.drives.by_drive_id.return_value.items.by_drive_item_id.return_value.children.post = AsyncMock(
            return_value=DriveItem(id="folder_id")
        )

        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.onedrive.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
