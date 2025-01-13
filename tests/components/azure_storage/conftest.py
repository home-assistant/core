"""Fixtures for Azure Storage tests."""

from collections.abc import AsyncIterator, Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from azure.storage.blob import BlobProperties
import pytest

from homeassistant.components.azure_storage.const import DOMAIN

from .const import BACKUP_METADATA, USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.azure_storage.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_blob_client() -> Mock:
    """Mock the Azure Storage blob client."""
    blob_client = Mock()
    blob_client.get_blob_properties = AsyncMock(
        return_value=BlobProperties(metadata=BACKUP_METADATA)
    )
    return blob_client


@pytest.fixture(autouse=True)
def mock_client(mock_blob_client: Mock) -> Generator[MagicMock]:
    """Mock the Azure Storage client."""
    with (
        patch(
            "homeassistant.components.azure_storage.config_flow.ContainerClient",
            autospec=True,
        ) as container_client,
        patch(
            "homeassistant.components.azure_storage.ContainerClient",
            new=container_client,
        ),
    ):
        client = container_client.return_value
        client.exists.return_value = True

        async def async_list_blobs():
            yield BlobProperties(metadata=BACKUP_METADATA)

        client.list_blobs.return_value = async_list_blobs()

        client.get_blob_client.return_value = mock_blob_client

        class MockStream:
            async def chunks(self) -> AsyncIterator[bytes]:
                yield b"backup data"

        client.download_blob.return_value = MockStream()

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="account/container1",
        domain=DOMAIN,
        data=USER_INPUT,
    )
