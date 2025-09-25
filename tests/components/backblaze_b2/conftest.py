"""Common fixtures for the Backblaze B2 tests."""

from collections.abc import Generator
import hashlib
import io
import json
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from b2sdk._internal.raw_simulator import BucketSimulator
from b2sdk.v2 import FileVersion, RawSimulator
import pytest

from homeassistant.components.backblaze_b2.const import (
    CONF_APPLICATION_KEY,
    CONF_BUCKET,
    CONF_KEY_ID,
    DOMAIN,
)
from homeassistant.components.backup import AgentBackup

from .const import BACKUP_METADATA, TEST_BACKUP, USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.backblaze_b2.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def b2_fixture():
    """Create account and application keys."""
    sim = RawSimulator()
    with (
        patch("b2sdk.v2.B2Api", return_value=sim) as mock_client,
        patch("homeassistant.components.backblaze_b2.B2Api", return_value=sim),
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
            {
                "backup_metadata": json.dumps(BACKUP_METADATA)
            },  # Store the full BACKUP_METADATA dict as user_file_info on the tar file
            stream_backup,
        )

        # --- Upload the metadata JSON file ---
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
                mock_response.content = self._content  # Add this line
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

        # Patch BucketSimulator to have the same attributes as real Bucket for diagnostics
        original_init = BucketSimulator.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            # Add attributes that match real Bucket class for diagnostics compatibility
            self.name = self.bucket_name
            self.id_ = self.bucket_id
            self.type_ = self.bucket_type
            self.cors_rules = []
            self.lifecycle_rules = []
            self.revision = 1

        BucketSimulator.__init__ = patched_init

        # Mock start_large_file and cancel_large_file for BucketSimulator
        def mock_start_large_file(
            file_name, content_type, file_info, account_auth_token
        ):
            del (
                content_type,
                file_info,
                account_auth_token,
            )  # Required by interface but not used
            mock_large_file = Mock()
            mock_large_file.file_name = file_name
            mock_large_file.file_id = "mock_file_id"
            return mock_large_file

        def mock_cancel_large_file(file_id, account_auth_token):
            del file_id, account_auth_token  # Required by interface but not used

        BucketSimulator.start_large_file = mock_start_large_file
        BucketSimulator.cancel_large_file = mock_cancel_large_file

        # Mock upload_local_file for the Bucket object - needed for direct file uploads
        def mock_upload_local_file(
            local_file,
            file_name,
            content_type=None,
            file_info=None,
            progress_listener=None,
        ):
            del progress_listener  # Required by interface but not used
            # Read the file content
            with open(local_file, "rb") as f:
                content = f.read()

            # Use the existing upload_file mock logic
            stream = io.BytesIO(content)
            stream.seek(0)
            return sim.upload_file(
                upload_url["uploadUrl"],
                upload_url["authorizationToken"],
                file_name,
                content_length=len(content),
                content_type=content_type or "application/octet-stream",
                content_sha1=None,
                file_info=file_info or {},
                data_stream=stream,
            )

        # We need to patch the actual Bucket class, not BucketSimulator
        import b2sdk.v2.bucket  # noqa: PLC0415

        original_upload_local_file = getattr(
            b2sdk.v2.bucket.Bucket, "upload_local_file", None
        )
        b2sdk.v2.bucket.Bucket.upload_local_file = mock_upload_local_file

        try:
            yield BackblazeFixture(
                application_key_id, application_key, bucket, sim, auth
            )
        finally:
            # Restore original method if it existed
            if original_upload_local_file is not None:
                b2sdk.v2.bucket.Bucket.upload_local_file = original_upload_local_file
            else:
                delattr(b2sdk.v2.bucket.Bucket, "upload_local_file")


@pytest.fixture
def backup_fixture(request: pytest.FixtureRequest) -> AgentBackup:
    """Test backup fixture."""
    del request  # Required by pytest but not used
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
    """Mock Backblaze B2 account."""

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

    def get_account_id(self):
        """Return account ID."""
        return "test_account_id"

    def get_api_url(self):
        """Return API URL."""
        return "https://api001.backblazeb2.com"

    def get_download_url(self):
        """Return download URL."""
        return "https://f001.backblazeb2.com"

    def get_minimum_part_size(self):
        """Return minimum part size."""
        return 5000000
