"""The tests for the notify file platform."""

import errno
import os
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.file import DOMAIN
from homeassistant.components.file.services import FileService, FileServiceArgument
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


@pytest.mark.parametrize(
    ("file_name", "file_encoding"),
    [
        ("tests/components/file/fixtures/file_read.json", "json"),
        ("tests/components/file/fixtures/file_read.yaml", "yaml"),
        ("tests/components/file/fixtures/file_read_list.yaml", "yaml"),
    ],
)
async def test_read_file(
    hass: HomeAssistant,
    mock_is_allowed_path: MagicMock,
    setup_ha_file_integration,
    file_name: str,
    file_encoding: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test reading files in supported formats."""
    result = await hass.services.async_call(
        DOMAIN,
        FileService.READ_FILE,
        {
            FileServiceArgument.FILE_NAME: file_name,
            FileServiceArgument.FILE_ENCODING: file_encoding,
        },
        blocking=True,
        return_response=True,
    )
    assert result == snapshot


async def test_read_file_disallowed_path(
    hass: HomeAssistant,
    setup_ha_file_integration,
) -> None:
    """Test reading in a disallowed path generates error."""
    file_name = "tests/components/file/fixtures/file_read.json"

    with pytest.raises(ServiceValidationError) as sve:
        await hass.services.async_call(
            DOMAIN,
            FileService.READ_FILE,
            {
                FileServiceArgument.FILE_NAME: file_name,
                FileServiceArgument.FILE_ENCODING: "json",
            },
            blocking=True,
            return_response=True,
        )
    assert file_name in str(sve.value)
    assert sve.value.translation_key == "no_access_to_path"
    assert sve.value.translation_domain == DOMAIN


async def test_read_file_bad_encoding_option(
    hass: HomeAssistant,
    mock_is_allowed_path: MagicMock,
    setup_ha_file_integration,
) -> None:
    """Test handling error if an invalid encoding is specified."""
    file_name = "tests/components/file/fixtures/file_read.json"

    with pytest.raises(ServiceValidationError) as sve:
        await hass.services.async_call(
            DOMAIN,
            FileService.READ_FILE,
            {
                FileServiceArgument.FILE_NAME: file_name,
                FileServiceArgument.FILE_ENCODING: "invalid",
            },
            blocking=True,
            return_response=True,
        )
    assert file_name in str(sve.value)
    assert "invalid" in str(sve.value)
    assert sve.value.translation_key == "unsupported_file_encoding"
    assert sve.value.translation_domain == DOMAIN


@pytest.mark.parametrize(
    ("file_name", "file_encoding"),
    [
        ("tests/components/file/fixtures/file_read.not_json", "json"),
        ("tests/components/file/fixtures/file_read.not_yaml", "yaml"),
    ],
)
async def test_read_file_decoding_error(
    hass: HomeAssistant,
    mock_is_allowed_path: MagicMock,
    setup_ha_file_integration,
    file_name: str,
    file_encoding: str,
) -> None:
    """Test decoding errors are handled correctly."""
    with pytest.raises(HomeAssistantError) as hae:
        await hass.services.async_call(
            DOMAIN,
            FileService.READ_FILE,
            {
                FileServiceArgument.FILE_NAME: file_name,
                FileServiceArgument.FILE_ENCODING: file_encoding,
            },
            blocking=True,
            return_response=True,
        )
    assert file_name in str(hae.value)
    assert file_encoding in str(hae.value)
    assert hae.value.translation_key == "file_decoding"
    assert hae.value.translation_domain == DOMAIN


@pytest.mark.parametrize(
    ("error_no", "translation_key"),
    [
        pytest.param(errno.ENOENT, "os_read_not_found", id="not_found"),
        pytest.param(errno.EACCES, "os_read_permission_denied", id="permission"),
        pytest.param(errno.EISDIR, "os_read_is_directory", id="is_directory"),
        pytest.param(errno.EIO, "os_read_error", id="fallback"),
    ],
)
async def test_read_file_os_errors(
    hass: HomeAssistant,
    mock_is_allowed_path: MagicMock,
    setup_ha_file_integration,
    error_no: int,
    translation_key: str,
) -> None:
    """Test handling the errors of reading the file."""
    file_name = "tests/components/file/fixtures/file_read.yaml"

    with (
        patch(
            "homeassistant.components.file.services.open",
            side_effect=OSError(error_no, os.strerror(error_no)),
        ),
        pytest.raises(HomeAssistantError) as hae,
    ):
        await hass.services.async_call(
            DOMAIN,
            FileService.READ_FILE,
            {
                FileServiceArgument.FILE_NAME: file_name,
                FileServiceArgument.FILE_ENCODING: "yaml",
            },
            blocking=True,
            return_response=True,
        )
    assert hae.value.translation_domain == "homeassistant"
    assert hae.value.translation_key == translation_key
    assert hae.value.translation_placeholders == {"path": file_name}
