"""Test the OSError translation helpers."""

import errno

import pytest

from homeassistant.helpers.os_error import os_error_translation_key


@pytest.mark.parametrize(
    ("err", "translation_key"),
    [
        pytest.param(
            PermissionError(errno.EACCES, "Permission denied"),
            "os_error_permission_denied",
            id="eacces",
        ),
        pytest.param(
            OSError(errno.EPERM, "Operation not permitted"),
            "os_error_permission_denied",
            id="eperm",
        ),
        pytest.param(
            OSError(errno.ENOSPC, "No space left on device"),
            "os_error_no_space",
            id="enospc",
        ),
        pytest.param(
            OSError(errno.EROFS, "Read-only file system"),
            "os_error_read_only",
            id="erofs",
        ),
        pytest.param(
            FileNotFoundError(errno.ENOENT, "No such file or directory"),
            "os_error_not_found",
            id="enoent",
        ),
        pytest.param(
            OSError(errno.EIO, "Input/output error"), "os_error", id="unmapped_errno"
        ),
        pytest.param(TimeoutError(), "os_error", id="no_errno"),
    ],
)
def test_os_error_translation_key(err: OSError, translation_key: str) -> None:
    """Test the translation key returned for an OSError."""
    assert os_error_translation_key(err) == translation_key
