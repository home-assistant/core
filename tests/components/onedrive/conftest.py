"""Fixtures for OneDrive tests."""

from collections.abc import AsyncIterator, Generator
from html import escape
from json import dumps
import time
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import Response
from msgraph.generated.models.drive_item import DriveItem
from msgraph.generated.models.drive_item_collection_response import (
    DriveItemCollectionResponse,
)
from msgraph.generated.models.upload_session import UploadSession
from msgraph_core.models import LargeFileUploadSession
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.onedrive.const import DOMAIN, OAUTH_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import BACKUP_METADATA, CLIENT_ID, CLIENT_SECRET

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
    )


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def mock_config_entry(expires_at: int, scopes: list[str]) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="John Doe's OneDrive",
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": " ".join(scopes),
            },
        },
        unique_id="mock_drive_id",
    )


@pytest.fixture
def mock_adapter() -> Generator[MagicMock]:
    """Return a mocked GraphAdapter."""
    with (
        patch(
            "homeassistant.components.onedrive.config_flow.GraphRequestAdapter",
            autospec=True,
        ) as mock_adapter,
        patch(
            "homeassistant.components.onedrive.backup.GraphRequestAdapter",
            new=mock_adapter,
        ),
    ):
        adapter = mock_adapter.return_value
        adapter.get_http_response_message.return_value = Response(
            status_code=200,
            json={
                "parentReference": {"driveId": "mock_drive_id"},
                "createdBy": {"user": {"displayName": "John Doe"}},
            },
        )
        yield adapter
        adapter.send_async.return_value = LargeFileUploadSession(
            next_expected_ranges=["2-"]
        )


@pytest.fixture(autouse=True)
def mock_graph_client(mock_adapter: MagicMock) -> Generator[MagicMock]:
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

        client.request_adapter = mock_adapter

        drives = client.drives.by_drive_id.return_value
        drives.special.by_drive_item_id.return_value.get = AsyncMock(
            return_value=DriveItem(id="approot")
        )

        drive_items = drives.items.by_drive_item_id.return_value
        drive_items.get = AsyncMock(return_value=DriveItem(id="folder_id"))
        drive_items.children.post = AsyncMock(return_value=DriveItem(id="folder_id"))
        drive_items.children.get = AsyncMock(
            return_value=DriveItemCollectionResponse(
                value=[
                    DriveItem(
                        id=BACKUP_METADATA["backup_id"],
                        description=escape(dumps(BACKUP_METADATA)),
                    ),
                    DriveItem(),
                ]
            )
        )
        drive_items.delete = AsyncMock(return_value=None)
        drive_items.create_upload_session.post = AsyncMock(
            return_value=UploadSession(upload_url="https://test.tld")
        )
        drive_items.patch = AsyncMock(return_value=None)

        async def generate_bytes() -> AsyncIterator[bytes]:
            """Asynchronous generator that yields bytes."""
            yield b"backup data"

        drive_items.content.get = AsyncMock(
            return_value=Response(status_code=200, content=generate_bytes())
        )

        yield client


@pytest.fixture
def mock_drive_items(mock_graph_client: MagicMock) -> MagicMock:
    """Return a mocked DriveItems."""
    return mock_graph_client.drives.by_drive_id.return_value.items.by_drive_item_id.return_value


@pytest.fixture
def mock_get_special_folder(mock_graph_client: MagicMock) -> MagicMock:
    """Mock the get special folder method."""
    return mock_graph_client.drives.by_drive_id.return_value.special.by_drive_item_id.return_value.get


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.onedrive.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_instance_id() -> Generator[AsyncMock]:
    """Mock the instance ID."""
    with patch(
        "homeassistant.components.onedrive.async_get_instance_id",
        return_value="9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0",
    ):
        yield


@pytest.fixture(autouse=True)
def mock_asyncio_sleep() -> Generator[AsyncMock]:
    """Mock asyncio.sleep."""
    with patch("homeassistant.components.onedrive.backup.asyncio.sleep", AsyncMock()):
        yield
