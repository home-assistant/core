"""Test downloader services."""

import asyncio
from contextlib import AbstractContextManager, nullcontext as does_not_raise

import pytest

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
