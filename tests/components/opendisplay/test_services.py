"""Test the OpenDisplay upload_image service."""

import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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


async def _setup_entry(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def _device_id(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> str:
    """Return the device registry ID for the config entry."""
    registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    assert devices
    return devices[0].id


def _mock_upload_device() -> AsyncMock:
    """Return a mock OpenDisplayDevice context manager."""
    mock_device = AsyncMock()
    mock_device.upload_image = AsyncMock()
    mock_device.__aenter__ = AsyncMock(return_value=mock_device)
    mock_device.__aexit__ = AsyncMock(return_value=False)
    return mock_device


async def test_upload_image_local_file(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    """Test successful upload from a local file."""
    await _setup_entry(hass, mock_config_entry)
    device_id = _device_id(hass, mock_config_entry)

    image_path = tmp_path / "test.png"
    PILImage.new("RGB", (100, 100), color="red").save(image_path)

    mock_media = MagicMock()
    mock_media.path = image_path
    mock_upload_dev = _mock_upload_device()

    with (
        patch(
            "homeassistant.components.opendisplay.services.async_resolve_media",
            return_value=mock_media,
        ),
        patch(
            "homeassistant.components.opendisplay.services.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.opendisplay.services.OpenDisplayDevice",
            return_value=mock_upload_dev,
        ),
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

    mock_upload_dev.upload_image.assert_called_once()


async def test_upload_image_remote_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    """Test successful upload from a remote URL."""
    await _setup_entry(hass, mock_config_entry)
    device_id = _device_id(hass, mock_config_entry)

    image = PILImage.new("RGB", (10, 10))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    image_bytes = buf.getvalue()

    mock_media = MagicMock()
    mock_media.path = None
    mock_media.url = "http://example.com/image.png"

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.read = AsyncMock(return_value=image_bytes)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    mock_upload_dev = _mock_upload_device()

    with (
        patch(
            "homeassistant.components.opendisplay.services.async_resolve_media",
            return_value=mock_media,
        ),
        patch(
            "homeassistant.components.opendisplay.services.async_get_clientsession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.opendisplay.services.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.opendisplay.services.OpenDisplayDevice",
            return_value=mock_upload_dev,
        ),
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

    mock_upload_dev.upload_image.assert_called_once()


async def test_upload_image_invalid_device_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an invalid device_id raises ServiceValidationError."""
    await _setup_entry(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
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
    """Test that ServiceValidationError is raised if device is out of BLE range."""
    await _setup_entry(hass, mock_config_entry)
    device_id = _device_id(hass, mock_config_entry)

    with (
        patch(
            "homeassistant.components.opendisplay.services.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(ServiceValidationError),
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
    tmp_path: Path,
) -> None:
    """Test that HomeAssistantError is raised on BLE upload failure."""
    await _setup_entry(hass, mock_config_entry)
    device_id = _device_id(hass, mock_config_entry)

    image_path = tmp_path / "test.png"
    PILImage.new("RGB", (10, 10)).save(image_path)

    mock_media = MagicMock()
    mock_media.path = image_path

    mock_upload_dev = AsyncMock()
    mock_upload_dev.__aenter__ = AsyncMock(
        side_effect=BLEConnectionError("connection lost")
    )
    mock_upload_dev.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "homeassistant.components.opendisplay.services.async_resolve_media",
            return_value=mock_media,
        ),
        patch(
            "homeassistant.components.opendisplay.services.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.opendisplay.services.OpenDisplayDevice",
            return_value=mock_upload_dev,
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


async def test_upload_image_download_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that ServiceValidationError is raised on media download failure."""
    await _setup_entry(hass, mock_config_entry)
    device_id = _device_id(hass, mock_config_entry)

    mock_media = MagicMock()
    mock_media.path = None
    mock_media.url = "http://example.com/image.png"

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientError("connection refused")
    )
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    with (
        patch(
            "homeassistant.components.opendisplay.services.async_resolve_media",
            return_value=mock_media,
        ),
        patch(
            "homeassistant.components.opendisplay.services.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.opendisplay.services.async_get_clientsession",
            return_value=mock_session,
        ),
        pytest.raises(ServiceValidationError),
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
    await _setup_entry(hass, mock_config_entry)
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
