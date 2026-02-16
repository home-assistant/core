"""Test the OpenDisplay image entity and upload_image service."""

import io
from pathlib import Path
from unittest.mock import AsyncMock, patch

from opendisplay import BLEConnectionError, BLETimeoutError, OpenDisplayError
from PIL import Image as PILImage
import pytest

from homeassistant.components.opendisplay.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

ENTITY_ID = "image.opendisplay_1234"


async def _setup_entry(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the config entry and wait for platforms."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def _mock_open_display_device() -> AsyncMock:
    """Create a mock OpenDisplayDevice context manager."""
    mock_device = AsyncMock()
    mock_device.upload_image = AsyncMock(return_value=PILImage.new("RGB", (10, 10)))
    mock_device.__aenter__ = AsyncMock(return_value=mock_device)
    mock_device.__aexit__ = AsyncMock(return_value=False)
    return mock_device


async def test_image_entity_created(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the image entity is created."""
    await _setup_entry(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None


async def test_image_entity_no_image_initially(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test image entity returns None when no image has been uploaded."""
    await _setup_entry(hass, mock_config_entry)

    entity = hass.data["image"].get_entity(ENTITY_ID)
    assert entity is not None
    image_bytes = await entity.async_image()
    assert image_bytes is None


async def test_upload_image_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmp_path: Path
) -> None:
    """Test successful image upload."""
    await _setup_entry(hass, mock_config_entry)

    # Create a test image file
    test_image = PILImage.new("RGB", (100, 100), color="red")
    image_path = tmp_path / "test.png"
    test_image.save(image_path)

    mock_device = _mock_open_display_device()
    mock_play_media = AsyncMock()
    mock_play_media.path = image_path

    with (
        patch(
            "homeassistant.components.opendisplay.image.async_resolve_media",
            return_value=mock_play_media,
        ),
        patch(
            "homeassistant.components.opendisplay.image.OpenDisplayDevice",
            return_value=mock_device,
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            "upload_image",
            {
                "image": {
                    "media_content_id": "media-source://local/test.png",
                    "media_content_type": "image/png",
                },
            },
            target={"entity_id": ENTITY_ID},
            blocking=True,
        )

    mock_device.upload_image.assert_awaited_once()

    # Verify the preview image was updated
    entity = hass.data["image"].get_entity(ENTITY_ID)
    image_bytes = await entity.async_image()
    assert image_bytes is not None
    assert len(image_bytes) > 0


async def test_upload_image_non_local_media(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmp_path: Path
) -> None:
    """Test upload works for non-local media sources via URL download."""
    await _setup_entry(hass, mock_config_entry)

    mock_play_media = AsyncMock()
    mock_play_media.path = None
    mock_play_media.url = "/immich/test/fullsize/image/jpeg"

    # Create test image bytes for the mock response
    test_image = PILImage.new("RGB", (100, 100), color="blue")
    buffer = io.BytesIO()
    test_image.save(buffer, format="PNG")
    image_data = buffer.getvalue()

    mock_response = AsyncMock()
    mock_response.read = AsyncMock(return_value=image_data)
    mock_response.raise_for_status = lambda: None

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_response)

    mock_device = _mock_open_display_device()

    with (
        patch(
            "homeassistant.components.opendisplay.image.async_resolve_media",
            return_value=mock_play_media,
        ),
        patch(
            "homeassistant.components.opendisplay.image.async_sign_path",
            return_value="/immich/test/fullsize/image/jpeg?signed=1",
        ),
        patch(
            "homeassistant.components.opendisplay.image.get_url",
            return_value="http://localhost:8123",
        ),
        patch(
            "homeassistant.components.opendisplay.image.async_get_clientsession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.opendisplay.image.OpenDisplayDevice",
            return_value=mock_device,
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            "upload_image",
            {
                "image": {
                    "media_content_id": "media-source://immich/test",
                    "media_content_type": "image/jpeg",
                },
            },
            target={"entity_id": ENTITY_ID},
            blocking=True,
        )

    mock_device.upload_image.assert_awaited_once()

    # Verify the preview image was updated
    entity = hass.data["image"].get_entity(ENTITY_ID)
    image_bytes = await entity.async_image()
    assert image_bytes is not None


async def test_upload_image_device_not_found(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmp_path: Path
) -> None:
    """Test upload fails when BLE device is not found."""
    await _setup_entry(hass, mock_config_entry)

    test_image = PILImage.new("RGB", (100, 100), color="red")
    image_path = tmp_path / "test.png"
    test_image.save(image_path)

    mock_play_media = AsyncMock()
    mock_play_media.path = image_path

    with (
        patch(
            "homeassistant.components.opendisplay.image.async_resolve_media",
            return_value=mock_play_media,
        ),
        patch(
            "homeassistant.components.opendisplay.image.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "upload_image",
            {
                "image": {
                    "media_content_id": "media-source://local/test.png",
                    "media_content_type": "image/png",
                },
            },
            target={"entity_id": ENTITY_ID},
            blocking=True,
        )


@pytest.mark.parametrize(
    "exception",
    [BLEConnectionError("timeout"), BLETimeoutError("timeout")],
)
async def test_upload_image_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
    exception: Exception,
) -> None:
    """Test upload fails on BLE connection errors."""
    await _setup_entry(hass, mock_config_entry)

    test_image = PILImage.new("RGB", (100, 100), color="red")
    image_path = tmp_path / "test.png"
    test_image.save(image_path)

    mock_device = _mock_open_display_device()
    mock_device.__aenter__.side_effect = exception

    mock_play_media = AsyncMock()
    mock_play_media.path = image_path

    with (
        patch(
            "homeassistant.components.opendisplay.image.async_resolve_media",
            return_value=mock_play_media,
        ),
        patch(
            "homeassistant.components.opendisplay.image.OpenDisplayDevice",
            return_value=mock_device,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "upload_image",
            {
                "image": {
                    "media_content_id": "media-source://local/test.png",
                    "media_content_type": "image/png",
                },
            },
            target={"entity_id": ENTITY_ID},
            blocking=True,
        )


async def test_upload_image_upload_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    """Test upload fails on OpenDisplay upload errors."""
    await _setup_entry(hass, mock_config_entry)

    test_image = PILImage.new("RGB", (100, 100), color="red")
    image_path = tmp_path / "test.png"
    test_image.save(image_path)

    mock_device = _mock_open_display_device()
    mock_device.upload_image.side_effect = OpenDisplayError("upload failed")

    mock_play_media = AsyncMock()
    mock_play_media.path = image_path

    with (
        patch(
            "homeassistant.components.opendisplay.image.async_resolve_media",
            return_value=mock_play_media,
        ),
        patch(
            "homeassistant.components.opendisplay.image.OpenDisplayDevice",
            return_value=mock_device,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "upload_image",
            {
                "image": {
                    "media_content_id": "media-source://local/test.png",
                    "media_content_type": "image/png",
                },
            },
            target={"entity_id": ENTITY_ID},
            blocking=True,
        )
