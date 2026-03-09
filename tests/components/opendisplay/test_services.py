"""Test the OpenDisplay upload_image service."""

import asyncio
from collections.abc import Generator
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import aiohttp
from opendisplay import BLEConnectionError
from PIL import Image as PILImage
import pytest
import voluptuous as vol

from homeassistant.components.opendisplay.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
async def setup_entry(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the config entry for service tests."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def mock_upload_device(mock_opendisplay_device: MagicMock) -> MagicMock:
    """Return the mock OpenDisplayDevice for upload service tests."""
    return mock_opendisplay_device


@pytest.fixture
def mock_resolve_media(tmp_path: Path) -> Generator[MagicMock]:
    """Mock async_resolve_media to return a local test image."""
    image_path = tmp_path / "test.png"
    PILImage.new("RGB", (10, 10)).save(image_path)
    mock_media = MagicMock()
    mock_media.path = image_path
    with patch(
        "homeassistant.components.opendisplay.services.async_resolve_media",
        return_value=mock_media,
    ):
        yield mock_media


def _device_id(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> str:
    """Return the device registry ID for the config entry."""
    registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    assert devices
    return devices[0].id


async def test_upload_image_local_file(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_upload_device: MagicMock,
    mock_resolve_media: MagicMock,
) -> None:
    """Test successful upload from a local file with tone compression."""
    device_id = _device_id(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        "upload_image",
        {
            "device_id": device_id,
            "image": {
                "media_content_id": "media-source://local/test.png",
                "media_content_type": "image/png",
            },
            "tone_compression": 50,
        },
        blocking=True,
    )

    mock_upload_device.upload_image.assert_called_once()


async def test_upload_image_remote_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_upload_device: MagicMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test successful upload from a remote URL."""
    device_id = _device_id(hass, mock_config_entry)

    image = PILImage.new("RGB", (10, 10))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    aioclient_mock.get("http://example.com/image.png", content=buf.getvalue())

    mock_media = MagicMock()
    mock_media.path = None
    mock_media.url = "http://example.com/image.png"

    with patch(
        "homeassistant.components.opendisplay.services.async_resolve_media",
        return_value=mock_media,
    ):
        await hass.services.async_call(
            DOMAIN,
            "upload_image",
            {
                "device_id": device_id,
                "image": {
                    "media_content_id": "media-source://local/test.png",
                    "media_content_type": "image/png",
                },
            },
            blocking=True,
        )

    mock_upload_device.upload_image.assert_called_once()


async def test_upload_image_invalid_device_id(
    hass: HomeAssistant,
) -> None:
    """Test that an invalid device_id raises ServiceValidationError."""
    with pytest.raises(ServiceValidationError, match="not a valid OpenDisplay device"):
        await hass.services.async_call(
            DOMAIN,
            "upload_image",
            {
                "device_id": "not-a-real-device-id",
                "image": {
                    "media_content_id": "media-source://local/test.png",
                    "media_content_type": "image/png",
                },
            },
            blocking=True,
        )


async def test_upload_image_device_not_in_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that HomeAssistantError is raised if device is out of BLE range."""
    device_id = _device_id(hass, mock_config_entry)

    with (
        patch(
            "homeassistant.components.opendisplay.services.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "upload_image",
            {
                "device_id": device_id,
                "image": {
                    "media_content_id": "media-source://local/test.png",
                    "media_content_type": "image/png",
                },
            },
            blocking=True,
        )


async def test_upload_image_ble_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opendisplay_device: MagicMock,
    mock_resolve_media: MagicMock,
) -> None:
    """Test that HomeAssistantError is raised on BLE upload failure."""
    device_id = _device_id(hass, mock_config_entry)

    mock_opendisplay_device.__aenter__.side_effect = BLEConnectionError(
        "connection lost"
    )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "upload_image",
            {
                "device_id": device_id,
                "image": {
                    "media_content_id": "media-source://local/test.png",
                    "media_content_type": "image/png",
                },
            },
            blocking=True,
        )


async def test_upload_image_download_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that HomeAssistantError is raised on media download failure."""
    device_id = _device_id(hass, mock_config_entry)

    aioclient_mock.get(
        "http://example.com/image.png",
        exc=aiohttp.ClientError("connection refused"),
    )

    mock_media = MagicMock()
    mock_media.path = None
    mock_media.url = "http://example.com/image.png"

    with (
        patch(
            "homeassistant.components.opendisplay.services.async_resolve_media",
            return_value=mock_media,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "upload_image",
            {
                "device_id": device_id,
                "image": {
                    "media_content_id": "media-source://local/test.png",
                    "media_content_type": "image/png",
                },
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    "field",
    ["dither_mode", "fit_mode", "refresh_mode"],
)
async def test_upload_image_invalid_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    field: str,
) -> None:
    """Test that invalid mode strings are rejected by the schema."""
    device_id = _device_id(hass, mock_config_entry)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "upload_image",
            {
                "device_id": device_id,
                "image": {
                    "media_content_id": "media-source://local/test.png",
                    "media_content_type": "image/png",
                },
                field: "not_a_valid_value",
            },
            blocking=True,
        )


async def test_upload_image_cancels_previous_task(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_upload_device: MagicMock,
    mock_resolve_media: MagicMock,
) -> None:
    """Test that starting a new upload cancels an in-progress upload task."""
    device_id = _device_id(hass, mock_config_entry)

    prev_task = hass.async_create_task(asyncio.sleep(3600))
    mock_config_entry.runtime_data.upload_task = prev_task

    await hass.services.async_call(
        DOMAIN,
        "upload_image",
        {
            "device_id": device_id,
            "image": {
                "media_content_id": "media-source://local/test.png",
                "media_content_type": "image/png",
            },
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert prev_task.cancelled()
