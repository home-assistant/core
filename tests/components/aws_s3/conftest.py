"""Common fixtures for the AWS S3 tests."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.aws_s3.backup import suggested_filenames
from homeassistant.components.aws_s3.const import DOMAIN
from homeassistant.components.backup import AgentBackup

from . import mock_streaming_body
from .const import CONFIG_ENTRY_DATA


@pytest.fixture
def backup_size() -> int:
    """Backup size, override in tests to change defaults."""
    return 2**20


@pytest.fixture
def backup_data() -> bytes:
    """Backup data, override in tests to change defaults."""
    return b"backup data"


@pytest.fixture
def backup_protected() -> bool:
    """Backup protected, override in tests to change defaults."""
    return False


@pytest.fixture
def mock_agent_backup(backup_size: int, backup_protected: bool) -> AgentBackup:
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
        protected=backup_protected,
        size=backup_size,
    )


@pytest.fixture(autouse=True)
def mock_client(
    mock_agent_backup: AgentBackup, backup_data: bytes
) -> Generator[AsyncMock]:
    """Mock the S3 client."""
    with patch(
        "aiobotocore.session.AioSession.create_client",
        autospec=True,
        return_value=AsyncMock(),
    ) as create_client:
        client = create_client.return_value

        tar_file, metadata_file = suggested_filenames(mock_agent_backup)

        # Mock the paginator for list_objects_v2
        client.get_paginator = MagicMock()
        paginate = client.get_paginator.return_value.paginate
        paginate.return_value.__aiter__.return_value = [
            {"Contents": [{"Key": tar_file}, {"Key": metadata_file}]}
        ]

        client.create_multipart_upload.return_value = {"UploadId": "upload_id"}
        client.upload_part.return_value = {"ETag": "etag"}

        objects = {
            tar_file: backup_data,
            metadata_file: json.dumps(mock_agent_backup.as_dict()).encode(),
        }
        client.get_object.side_effect = lambda **kwargs: {
            "Body": mock_streaming_body(objects[kwargs["Key"].rsplit("/", 1)[-1]])
        }
        client.head_bucket.return_value = {}

        create_client.return_value.__aenter__.return_value = client
        yield client


@pytest.fixture
def config_entry_extra_data() -> dict:
    """Extra config entry data, override in tests to change defaults."""
    return {}


@pytest.fixture
def mock_config_entry(config_entry_extra_data: dict) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        entry_id="test",
        title="test",
        domain=DOMAIN,
        data=CONFIG_ENTRY_DATA | config_entry_extra_data,
    )
