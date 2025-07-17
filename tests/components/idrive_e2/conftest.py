"""Common fixtures for the IDrive e2 tests."""

from collections.abc import Generator
import json
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.backup import AgentBackup
from homeassistant.components.idrive_e2.backup import (
    MULTIPART_MIN_PART_SIZE_BYTES,
    suggested_filenames,
)
from homeassistant.components.idrive_e2.const import DOMAIN

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
def mock_client(test_backup: AgentBackup) -> Generator[MagicMock]:
    """Mock the IDrive e2 client."""
    with patch(
        "boto3.session.Session.client",
        autospec=True,
        return_value=MagicMock(),
    ) as create_client:
        client = create_client.return_value

        tar_file, metadata_file = suggested_filenames(test_backup)
        client.list_objects_v2.return_value = {
            "Contents": [{"Key": tar_file}, {"Key": metadata_file}]
        }
        client.create_multipart_upload.return_value = {"UploadId": "upload_id"}
        client.upload_part.return_value = {"ETag": "etag"}

        # To simplify this mock, we assume that backup is always "iterated" over, while metadata is always "read" as a whole
        class MockStream:
            def iter_chunks(self):
                yield b"backup data"

            def read(self) -> bytes:
                return json.dumps(test_backup.as_dict()).encode()

        client.get_object.return_value = {"Body": MockStream()}
        client.head_bucket.return_value = {}

        # create_client.return_value = client
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
