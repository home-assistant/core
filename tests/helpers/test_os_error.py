"""Test the OSError helpers."""

import errno

import pytest

from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.helpers.os_error import os_write_error


@pytest.mark.parametrize(
    ("err", "translation_key"),
    [
        pytest.param(
            PermissionError(errno.EACCES, "Permission denied"),
            "os_write_permission_denied",
            id="eacces",
        ),
        pytest.param(
            OSError(errno.EPERM, "Operation not permitted"),
            "os_write_permission_denied",
            id="eperm",
        ),
        pytest.param(
            OSError(errno.ENOSPC, "No space left on device"),
            "os_write_no_space",
            id="enospc",
        ),
        pytest.param(
            OSError(errno.EROFS, "Read-only file system"),
            "os_write_read_only",
            id="erofs",
        ),
        pytest.param(
            FileNotFoundError(errno.ENOENT, "No such file or directory"),
            "os_write_dir_not_found",
            id="enoent",
        ),
        pytest.param(
            OSError(errno.EIO, "Input/output error"),
            "os_write_error",
            id="unmapped_errno",
        ),
        pytest.param(TimeoutError(), "os_write_error", id="no_errno"),
    ],
)
def test_os_write_error(err: OSError, translation_key: str) -> None:
    """Test the error returned for an OSError raised while writing."""
    error = os_write_error(err, "/test/file.txt")

    assert error.translation_domain == HOMEASSISTANT_DOMAIN
    assert error.translation_key == translation_key
    assert error.translation_placeholders == {"path": "/test/file.txt"}
