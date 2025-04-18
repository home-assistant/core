"""Common fixtures for the S3 tests."""

from collections.abc import AsyncIterator, Generator
import json
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.s3.backup import suggested_filenames
from homeassistant.components.s3.const import DOMAIN

from .const import TEST_BACKUP, USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_client() -> Generator[AsyncMock]:
    """Mock the S3 client."""
    with patch(
        "homeassistant.components.s3.api.AioSession.create_client",
        autospec=True,
        return_value=AsyncMock(),
    ) as create_client:
        client = create_client.return_value

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

        create_client.return_value.__aenter__.return_value = client
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        entry_id="test",
        title="test",
        domain=DOMAIN,
        data=USER_INPUT,
    )
