"""Common fixtures for the Backblaze tests."""

from collections.abc import Generator
import hashlib
import io
import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from b2sdk._internal.raw_simulator import BucketSimulator
from b2sdk.v2 import FileVersion, RawSimulator
import pytest

from homeassistant.components.backblaze.const import (
    CONF_APPLICATION_KEY,
    CONF_BUCKET,
    CONF_KEY_ID,
    DOMAIN,
)

from .const import BACKUP_METADATA, TEST_BACKUP, USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.backblaze.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def b2_fixture():
    """Create account and application keys."""
    sim = RawSimulator()
    with (
        patch("b2sdk.v2.B2Api", return_value=sim) as mock_client,
        patch("homeassistant.components.backblaze.B2Api", return_value=sim),
    ):
        RawSimulator.get_bucket_by_name = RawSimulator._get_bucket_by_name

        allowed = {
            "capabilities": [
                "writeFiles",
                "listFiles",
                "deleteFiles",
                "readFiles",
            ]
        }
        RawSimulator.account_info = AccountInfo(allowed)

        sim: RawSimulator = mock_client.return_value
        account_id, application_key = sim.create_account()
        auth = sim.authorize_account("production", account_id, application_key)
        auth_token: str = auth["authorizationToken"]
        api_url: str = auth["apiInfo"]["storageApi"]["apiUrl"]

        key = sim.create_key(
            api_url=api_url,
            account_auth_token=auth_token,
            account_id=account_id,
            key_name="testkey",
            capabilities=[
                "writeFiles",
                "listFiles",
                "deleteFiles",
                "readFiles",
            ],
            valid_duration_seconds=None,
            bucket_id=None,
            name_prefix=None,
        )

        application_key_id: str = key["applicationKeyId"]
        application_key: str = key[
            "applicationKey"
        ]  # Corrected typo based on prev conversation

        bucket = sim.create_bucket(
            api_url=api_url,
            account_id=account_id,
            account_auth_token=auth_token,
            bucket_name=USER_INPUT[CONF_BUCKET],
            bucket_type="allPrivate",
        )

        upload_url = sim.get_upload_url(api_url, auth_token, bucket["bucketId"])

        # --- Upload the main backup file (e.g., .tar) ---
        test_backup_data = b"This is the actual backup data for the tar file."
        stream_backup = io.BytesIO(test_backup_data)
        stream_backup.seek(0)

        # The filename of the backup archive is based on TEST_BACKUP.backup_id
        backup_filename = (
            f"{TEST_BACKUP.backup_id}.tar"  # Ensure it starts with backup_id
        )
        sha1_backup = hashlib.sha1(test_backup_data).hexdigest()

        file_backup_upload_result = sim.upload_file(
            upload_url["uploadUrl"],
            upload_url["authorizationToken"],
            f"testprefix/{backup_filename}",
            len(test_backup_data),
            "application/octet-stream",
            sha1_backup,
            {},  # Store the full BACKUP_METADATA dict as user_file_info on the tar file
            stream_backup,
        )

        # --- Upload the metadata JSON file ---
        # The content of the metadata JSON file is BACKUP_METADATA["backup_metadata"]
        # which is already a JSON string from TEST_BACKUP.as_dict()
        metadata_json_content_bytes = json.dumps(BACKUP_METADATA).encode("utf-8")
        stream_metadata = io.BytesIO(metadata_json_content_bytes)
        stream_metadata.seek(0)

        # The filename for the metadata JSON is based on TEST_BACKUP.backup_id
        metadata_filename = f"{TEST_BACKUP.backup_id}.metadata.json"
        sha1_metadata = hashlib.sha1(metadata_json_content_bytes).hexdigest()

        file_metadata_upload_result = sim.upload_file(
            upload_url["uploadUrl"],
            upload_url["authorizationToken"],
            f"testprefix/{metadata_filename}",
            len(metadata_json_content_bytes),
            "application/json",  # Explicitly set content type to JSON
            sha1_metadata,
            {},  # No custom user metadata for the metadata file itself
            stream_metadata,
        )

        # Store all uploaded file results for the ls mock
        uploaded_files_results = [
            file_backup_upload_result,
            file_metadata_upload_result,
        ]

        # Define a mock for DownloadedFile
        class MockDownloadedFile:
            def __init__(self, content: bytes) -> None:
                self._content = content

            @property
            def text_content(self) -> str:
                return self._content.decode("utf-8")

            @property
            def response(self):
                # This is a simplified mock for the response object
                # It should provide an iter_content method that yields the content
                mock_response = Mock()
                mock_response.iter_content.return_value = iter([self._content])
                return mock_response

        # Define a mock for download_file_by_id on RawSimulator
        def mock_sim_download_file_by_id(
            file_id,
            file_name=None,
            progress_listener=None,
            range_=None,
            encryption=None,
        ):
            for file_data in uploaded_files_results:
                if file_data["fileId"] == file_id or (
                    file_name and file_data["fileName"] == file_name
                ):
                    if file_data["fileName"].endswith(".metadata.json"):
                        return MockDownloadedFile(metadata_json_content_bytes)
                    return MockDownloadedFile(test_backup_data)
            raise ValueError(
                f"Mocked download_file_by_id: File with id {file_id} or name {file_name} not found."
            )

        # Assign the mock method to the RawSimulator instance
        sim.download_file_by_id = mock_sim_download_file_by_id

        # --- Modify the ls mock to return ALL uploaded files ---
        def ls(
            self,
            prefix: str = "",
        ) -> list[tuple[FileVersion, str]]:
            """List files in the bucket."""
            listed_files = []
            for file_data in uploaded_files_results:
                if prefix and not file_data["fileName"].startswith(prefix):
                    continue

                listed_files.append(
                    (
                        FileVersion(
                            sim,
                            file_data["fileId"],
                            file_data["fileName"],
                            file_data["contentLength"],
                            file_data.get("contentType", "application/octet-stream"),
                            file_data["fileInfo"].get("sha1", ""),
                            file_data[
                                "fileInfo"
                            ],  # Use the fileInfo stored during upload
                            file_data["uploadTimestamp"],
                            file_data["accountId"],
                            file_data["bucketId"],
                            "upload",
                            None,
                            None,
                        ),
                        file_data["fileName"],
                    )
                )
            return listed_files

        BucketSimulator.ls = ls

        yield BackblazeFixture(application_key_id, application_key, bucket, sim, auth)


@pytest.fixture
def test_backup(request: pytest.FixtureRequest) -> None:
    """Test backup fixture."""
    return TEST_BACKUP


@pytest.fixture
def mock_config_entry(b2_fixture: Any) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        entry_id="c6dd4663ec2c75fe04701be54c03f27b",
        title="test",
        domain=DOMAIN,
        data={
            **USER_INPUT,
            CONF_KEY_ID: b2_fixture.key_id,
            CONF_APPLICATION_KEY: b2_fixture.application_key,
        },
    )


class BackblazeFixture:
    """Mock Backblaze account."""

    def __init__(  # noqa: D107
        self,
        key_id: str,
        application_key: str,
        bucket: dict[str, Any],
        sim: RawSimulator,
        auth: dict[str, Any],
    ) -> None:
        self.key_id = key_id
        self.application_key = application_key
        self.bucket = bucket
        self.sim = sim
        self.auth = auth
        self.api_url = auth["apiInfo"]["storageApi"]["apiUrl"]
        self.account_id = auth["accountId"]


class AccountInfo:
    """Mock account info."""

    def __init__(self, allowed: dict[str, Any]) -> None:  # noqa: D107
        self._allowed = allowed

    def get_allowed(self):
        """Return allowed capabilities."""
        return self._allowed
