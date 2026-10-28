"""Test the OSError helpers."""

import errno

import pytest

from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.os_error import os_read_error, os_write_error
from homeassistant.helpers.translation import async_load_integrations


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


@pytest.mark.parametrize(
    ("err", "error_class", "translation_key", "message"),
    [
        pytest.param(
            FileNotFoundError(errno.ENOENT, "No such file or directory"),
            ServiceValidationError,
            "os_read_not_found",
            "Cannot read /test/file.txt: the file does not exist",
            id="enoent",
        ),
        pytest.param(
            PermissionError(errno.EACCES, "Permission denied"),
            HomeAssistantError,
            "os_read_permission_denied",
            "Cannot read /test/file.txt: permission denied",
            id="eacces",
        ),
        pytest.param(
            OSError(errno.EPERM, "Operation not permitted"),
            HomeAssistantError,
            "os_read_permission_denied",
            "Cannot read /test/file.txt: permission denied",
            id="eperm",
        ),
        pytest.param(
            IsADirectoryError(errno.EISDIR, "Is a directory"),
            HomeAssistantError,
            "os_read_is_directory",
            "Cannot read /test/file.txt: it is a folder, not a file",
            id="eisdir",
        ),
        pytest.param(
            OSError(errno.EIO, "Input/output error"),
            HomeAssistantError,
            "os_read_error",
            "Cannot read /test/file.txt",
            id="unmapped_errno",
        ),
        pytest.param(
            TimeoutError(),
            HomeAssistantError,
            "os_read_error",
            "Cannot read /test/file.txt",
            id="no_errno",
        ),
    ],
)
async def test_os_read_error(
    hass: HomeAssistant,
    err: OSError,
    error_class: type[HomeAssistantError],
    translation_key: str,
    message: str,
) -> None:
    """Test the error returned for an OSError raised while reading."""
    await async_load_integrations(hass, {HOMEASSISTANT_DOMAIN})

    error = os_read_error(err, "/test/file.txt")

    assert type(error) is error_class
    assert error.translation_domain == HOMEASSISTANT_DOMAIN
    assert error.translation_key == translation_key
    assert error.translation_placeholders == {"path": "/test/file.txt"}
    assert str(error) == message
