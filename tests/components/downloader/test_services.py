"""Test downloader services."""

import asyncio
from contextlib import AbstractContextManager, nullcontext as does_not_raise

import pytest
from requests_mock import Mocker
import voluptuous as vol

from homeassistant.components.downloader.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError


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
        (1, pytest.raises(vol.error.Invalid)),  # Not a dictionary
        ({"Accept": "application/json"}, does_not_raise()),
        ({123: 456.789}, does_not_raise()),  # Convert numbers to strings
        (
            {"Accept": ["application/json"]},
            pytest.raises(vol.error.MultipleInvalid),
        ),  # Value is not a string
        ({1: None}, pytest.raises(vol.error.MultipleInvalid)),  # Value is None
        (
            {None: "application/json"},
            pytest.raises(vol.error.MultipleInvalid),
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
