"""Test downloader services."""

import asyncio
from contextlib import AbstractContextManager, nullcontext as does_not_raise
import errno
from pathlib import Path
from types import TracebackType
from typing import Self
from unittest.mock import patch

import probatio
import pytest
import requests
from requests_mock import Mocker

from homeassistant.components.downloader.const import DOMAIN, DOWNLOAD_FAILED_EVENT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import async_capture_events

OS_WRITE_ERRORS = [
    pytest.param(errno.EACCES, "os_write_permission_denied", id="EACCES"),
    pytest.param(errno.ENOSPC, "os_write_no_space", id="ENOSPC"),
    pytest.param(errno.EROFS, "os_write_read_only", id="EROFS"),
    pytest.param(errno.ENOENT, "os_write_dir_not_found", id="ENOENT"),
    pytest.param(errno.EIO, "os_write_error", id="EIO"),
]


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("subdir", "expected_result"),
    [
        ("test", does_not_raise()),
        ("test/path", does_not_raise()),
        ("~test/path", pytest.raises(ServiceValidationError)),
        ("~/../test/path", pytest.raises(ServiceValidationError)),
        ("../test/path", pytest.raises(ServiceValidationError)),
        (".../test/path", pytest.raises(ServiceValidationError)),
        ("/test/path", pytest.raises(ServiceValidationError)),
    ],
)
async def test_download_invalid_subdir(
    hass: HomeAssistant,
    download_completed: asyncio.Event,
    download_failed: asyncio.Event,
    download_url: str,
    subdir: str,
    expected_result: AbstractContextManager,
) -> None:
    """Test service invalid subdirectory."""

    async def call_service() -> None:
        """Call the download service."""
        completed = hass.async_create_task(download_completed.wait())
        failed = hass.async_create_task(download_failed.wait())
        await hass.services.async_call(
            DOMAIN,
            "download_file",
            {
                "url": download_url,
                "subdir": subdir,
                "filename": "file.txt",
                "overwrite": True,
            },
            blocking=True,
        )
        await asyncio.wait((completed, failed), return_when=asyncio.FIRST_COMPLETED)

    with expected_result:
        await call_service()


@pytest.mark.usefixtures("setup_integration")
async def test_download_headers_passed_through(
    hass: HomeAssistant,
    requests_mock: Mocker,
    download_completed: asyncio.Event,
    download_url: str,
) -> None:
    """Test that custom headers are passed to the HTTP request."""
    await hass.services.async_call(
        DOMAIN,
        "download_file",
        {
            "url": download_url,
            "headers": {"Authorization": "Bearer token123", "X-Custom": "value"},
        },
        blocking=True,
    )
    await download_completed.wait()

    assert requests_mock.last_request.headers["Authorization"] == "Bearer token123"
    assert requests_mock.last_request.headers["X-Custom"] == "value"


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("headers", "expected_result"),
    [
        (1, pytest.raises(probatio.error.Invalid)),  # Not a dictionary
        ({"Accept": "application/json"}, does_not_raise()),
        ({123: 456.789}, does_not_raise()),  # Convert numbers to strings
        (
            {"Accept": ["application/json"]},
            pytest.raises(probatio.error.MultipleInvalid),
        ),  # Value is not a string
        ({1: None}, pytest.raises(probatio.error.MultipleInvalid)),  # Value is None
        (
            {None: "application/json"},
            pytest.raises(probatio.error.MultipleInvalid),
        ),  # Key is None
    ],
)
async def test_download_headers_schema(
    hass: HomeAssistant,
    download_completed: asyncio.Event,
    download_failed: asyncio.Event,
    download_url: str,
    headers: dict[str, str],
    expected_result: AbstractContextManager,
) -> None:
    """Test service with headers."""

    async def call_service() -> None:
        """Call the download service."""
        completed = hass.async_create_task(download_completed.wait())
        failed = hass.async_create_task(download_failed.wait())
        await hass.services.async_call(
            DOMAIN,
            "download_file",
            {
                "url": download_url,
                "headers": headers,
                "subdir": "test",
                "filename": "file.txt",
                "overwrite": True,
            },
            blocking=True,
        )
        await asyncio.wait((completed, failed), return_when=asyncio.FIRST_COMPLETED)

    with expected_result:
        await call_service()


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        pytest.param(
            requests.exceptions.ConnectionError,
            HomeAssistantError,
            id="connection_error",
        ),
        pytest.param(
            ValueError,
            ServiceValidationError,
            id="value_error",
        ),
    ],
)
async def test_download_exceptions(
    hass: HomeAssistant,
    requests_mock: Mocker,
    download_url: str,
    download_failed: asyncio.Event,
    exception: type[Exception],
    expected_error: type[Exception],
) -> None:
    """Test that exceptions during download propagate to the caller."""
    requests_mock.get(download_url, exc=exception)
    with pytest.raises(expected_error):
        await hass.services.async_call(
            DOMAIN, "download_file", {"url": download_url}, blocking=True
        )
    await download_failed.wait()


class FailingFile:
    """File that writes part of the download and then fails."""

    def __init__(self, path: str, mode: str, error: OSError) -> None:
        """Open the real file."""
        self._file = open(path, mode)  # pylint: disable=consider-using-with
        self._error = error

    def __enter__(self) -> Self:
        """Enter the context."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the real file."""
        self._file.close()

    def writelines(self, lines: object) -> None:
        """Write a partial download, then fail."""
        self._file.write(b"partial")
        raise self._error


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(("error_number", "translation_key"), OS_WRITE_ERRORS)
async def test_download_subdir_create_error(
    hass: HomeAssistant,
    download_dir: Path,
    download_url: str,
    error_number: int,
    translation_key: str,
) -> None:
    """Test a translated error when the subdirectory can't be created."""
    events = async_capture_events(hass, f"{DOMAIN}_{DOWNLOAD_FAILED_EVENT}")
    with (
        patch(
            "homeassistant.components.downloader.services.os.makedirs",
            side_effect=OSError(error_number, "error"),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            "download_file",
            {"url": download_url, "subdir": "test", "filename": "file.txt"},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert exc_info.value.translation_domain == "homeassistant"
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == {
        "path": str(download_dir / "test")
    }
    assert [event.data for event in events] == [
        {"url": download_url, "filename": "file.txt"}
    ]
    assert list(download_dir.iterdir()) == []


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(("error_number", "translation_key"), OS_WRITE_ERRORS)
async def test_download_write_error(
    hass: HomeAssistant,
    download_dir: Path,
    download_url: str,
    error_number: int,
    translation_key: str,
) -> None:
    """Test a translated error and no partial file when writing fails."""
    events = async_capture_events(hass, f"{DOMAIN}_{DOWNLOAD_FAILED_EVENT}")
    with (
        patch(
            "homeassistant.components.downloader.services.open",
            side_effect=lambda path, mode: FailingFile(
                path, mode, OSError(error_number, "error")
            ),
            create=True,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            "download_file",
            {"url": download_url, "filename": "file.txt"},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert exc_info.value.translation_domain == "homeassistant"
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders == {
        "path": str(download_dir / "file.txt")
    }
    assert [event.data for event in events] == [
        {"url": download_url, "filename": "file.txt"}
    ]
    assert list(download_dir.iterdir()) == []


@pytest.mark.usefixtures("setup_integration")
async def test_download_open_error_keeps_existing_file(
    hass: HomeAssistant,
    download_dir: Path,
    download_url: str,
) -> None:
    """Test an existing file is kept when it can't be opened for writing."""
    existing_file = download_dir / "file.txt"
    existing_file.write_text("existing")
    events = async_capture_events(hass, f"{DOMAIN}_{DOWNLOAD_FAILED_EVENT}")
    with (
        patch(
            "homeassistant.components.downloader.services.open",
            side_effect=OSError(errno.EACCES, "error"),
            create=True,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            "download_file",
            {"url": download_url, "filename": "file.txt", "overwrite": True},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert exc_info.value.translation_key == "os_write_permission_denied"
    assert [event.data for event in events] == [
        {"url": download_url, "filename": "file.txt"}
    ]
    assert existing_file.read_text() == "existing"


@pytest.mark.usefixtures("setup_integration")
async def test_download_connection_error_while_writing(
    hass: HomeAssistant,
    download_dir: Path,
    download_url: str,
) -> None:
    """Test a connection error during the download isn't reported as a write error."""
    events = async_capture_events(hass, f"{DOMAIN}_{DOWNLOAD_FAILED_EVENT}")
    with (
        patch(
            "homeassistant.components.downloader.services.open",
            side_effect=lambda path, mode: FailingFile(
                path, mode, requests.exceptions.ConnectionError()
            ),
            create=True,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            "download_file",
            {"url": download_url, "filename": "file.txt"},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "connection_error"
    assert len(events) == 1
    assert list(download_dir.iterdir()) == []
