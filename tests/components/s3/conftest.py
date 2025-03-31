"""Common fixtures for the S3 tests."""

from collections.abc import AsyncIterator, Generator
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.s3.backup import suggested_filenames
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
            return_value=AsyncMock(),
        ) as get_client,
        patch("homeassistant.components.s3.get_client", new=get_client),
    ):
        client = get_client.return_value
        tar_file, metadata_file = suggested_filenames(TEST_BACKUP)
        client.list_objects_v2.return_value = {
            "Contents": [{"Key": tar_file}, {"Key": metadata_file}]
        }
        client.create_multipart_upload.return_value = {"UploadId": "upload_id"}
        client.upload_part.return_value = {"ETag": "etag"}

        # to simplify this mock, we assume that backup is always "iterated" over, while metadata is always "read" as a whole
        class MockStream:
            async def iter_chunks(self) -> AsyncIterator[bytes]:
                yield b"backup data"

            async def read(self) -> bytes:
                return json.dumps(TEST_BACKUP.as_dict()).encode()

        client.get_object.return_value = {"Body": MockStream()}

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
