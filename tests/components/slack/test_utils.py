"""Test the Slack utils."""

import errno
import os
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.slack.utils import upload_file_to_slack
from homeassistant.exceptions import HomeAssistantError


@pytest.mark.parametrize(
    ("error_no", "translation_key"),
    [
        pytest.param(errno.ENOENT, "os_read_not_found", id="not_found"),
        pytest.param(errno.EACCES, "os_read_permission_denied", id="permission"),
        pytest.param(errno.EISDIR, "os_read_is_directory", id="is_directory"),
        pytest.param(errno.EIO, "os_read_error", id="fallback"),
    ],
)
async def test_upload_file_read_error(error_no: int, translation_key: str) -> None:
    """Test that a local file read error raises and uploads nothing."""
    client = AsyncMock()

    with (
        patch(
            "homeassistant.components.slack.utils.aiofiles.open",
            side_effect=OSError(error_no, os.strerror(error_no)),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await upload_file_to_slack(
            client=client,
            channel_ids=["C1"],
            file_content=None,
            filename="file.jpg",
            title=None,
            message="test",
            thread_ts=None,
            file_path="/some/file.jpg",
        )

    assert exc_info.value.translation_domain == "homeassistant"
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == {"path": "/some/file.jpg"}
    client.files_upload_v2.assert_not_called()
