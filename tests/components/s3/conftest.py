"""Common fixtures for the S3 tests."""

from collections.abc import AsyncIterator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.s3.backup import _get_key, _serialize
from homeassistant.components.s3.const import DOMAIN

from .const import TEST_BACKUP, USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.s3.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_client() -> Generator[MagicMock]:
    """Mock the S3 client."""
    with (
        patch(
            "homeassistant.components.s3.config_flow.get_client",
            autospec=True,
        ) as get_client,
        patch("homeassistant.components.s3.get_client", new=get_client),
    ):
        client = get_client.return_value
        client.list_objects_v2 = AsyncMock(
            return_value={"Contents": [{"Key": _get_key(TEST_BACKUP)}]}
        )
        client.head_object = AsyncMock(
            return_value={
                "Metadata": _serialize(
                    {
                        "metadata_version": "1",
                        "backup_metadata": TEST_BACKUP.as_dict(),
                    }
                )
            }
        )
        client.delete_object = AsyncMock()
        client.create_multipart_upload = AsyncMock(
            return_value={"UploadId": "upload_id"}
        )
        client.upload_part = AsyncMock(return_value={"ETag": "etag"})
        client.complete_multipart_upload = AsyncMock()
        client.abort_multipart_upload = AsyncMock()

        class MockStream:
            async def iter_chunks(self) -> AsyncIterator[bytes]:
                yield b"backup data"

        client.get_object = AsyncMock(return_value={"Body": MockStream()})

        get_client.return_value.__aenter__.return_value = client
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        unique_id="test",
        entry_id="test",
        title="test",
        domain=DOMAIN,
        data=USER_INPUT,
    )
