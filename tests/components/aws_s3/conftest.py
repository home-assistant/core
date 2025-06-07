"""Common fixtures for the AWS S3 tests."""

from collections.abc import AsyncIterator, Generator
import json
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.aws_s3.backup import (
    MULTIPART_MIN_PART_SIZE_BYTES,
    suggested_filenames,
)
from homeassistant.components.aws_s3.const import DOMAIN
from homeassistant.components.backup import AgentBackup

from .const import USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture(
    params=[2**20, MULTIPART_MIN_PART_SIZE_BYTES],
    ids=["small", "large"],
)
def test_backup(request: pytest.FixtureRequest) -> None:
    """Test backup fixture."""
    return AgentBackup(
        addons=[],
        backup_id="23e64aec",
        date="2024-11-22T11:48:48.727189+01:00",
        database_included=True,
        extra_metadata={},
        folders=[],
        homeassistant_included=True,
        homeassistant_version="2024.12.0.dev0",
        name="Core 2024.12.0.dev0",
        protected=False,
        size=request.param,
    )


@pytest.fixture(autouse=True)
def mock_client(test_backup: AgentBackup) -> Generator[AsyncMock]:
    """Mock the S3 client."""
    with patch(
        "aiobotocore.session.AioSession.create_client",
        autospec=True,
        return_value=AsyncMock(),
    ) as create_client:
        client = create_client.return_value

        tar_file, metadata_file = suggested_filenames(test_backup)
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
                return json.dumps(test_backup.as_dict()).encode()

        client.get_object.return_value = {"Body": MockStream()}
        client.head_bucket.return_value = {}

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
