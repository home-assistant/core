"""Test the OpenDisplay image entity and upload_image service."""

import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from opendisplay import BLEConnectionError, RefreshMode
from PIL import Image as PILImage
import pytest

from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.opendisplay.const import DOMAIN
from homeassistant.components.opendisplay.entity import OpenDisplayImageExtraStoredData
from homeassistant.components.opendisplay.image import OpenDisplayImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import async_get_platforms

from . import make_service_info

from tests.common import MockConfigEntry

ENTITY_ID = "image.opendisplay_1234"

# Fake prepare_image result: (uncompressed, compressed, processed_pil)
FAKE_PREPARED = (b"\x00" * 100, b"\x01" * 50, PILImage.new("RGB", (10, 10)))


def _get_entity(hass: HomeAssistant) -> OpenDisplayImageEntity:
    """Get the OpenDisplay image entity via entity platform."""
    platforms = async_get_platforms(hass, DOMAIN)
    assert platforms
    entity = platforms[0].entities[ENTITY_ID]
    assert isinstance(entity, OpenDisplayImageEntity)
    return entity


async def _setup_entry(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the config entry and wait for platforms."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def _mock_upload_device() -> AsyncMock:
    """Create a mock OpenDisplayDevice for BLE upload (context manager)."""
    mock_device = AsyncMock()
    mock_device.upload_prepared_image = AsyncMock()
    mock_device.__aenter__ = AsyncMock(return_value=mock_device)
    mock_device.__aexit__ = AsyncMock(return_value=False)
    return mock_device


async def test_image_entity_no_image_initially(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test image entity returns None when no image has been uploaded."""
    await _setup_entry(hass, mock_config_entry)

    entity = _get_entity(hass)
    image_bytes = await entity.async_image()
    assert image_bytes is None


async def test_upload_image_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmp_path: Path
) -> None:
    """Test successful image upload updates entity immediately."""
    await _setup_entry(hass, mock_config_entry)

    # Create a test image file
    test_image = PILImage.new("RGB", (100, 100), color="red")
    image_path = tmp_path / "test.png"
    test_image.save(image_path)

    mock_play_media = AsyncMock()
    mock_play_media.path = image_path

    mock_upload_dev = _mock_upload_device()

    with (
        patch(
            "homeassistant.components.opendisplay.image.async_resolve_media",
            return_value=mock_play_media,
        ),
        patch(
            "homeassistant.components.opendisplay.image.prepare_image",
            return_value=FAKE_PREPARED,
        ),
        patch(
            "homeassistant.components.opendisplay.image.OpenDisplayDevice",
            return_value=mock_upload_dev,
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
        await hass.async_block_till_done()

    mock_upload_dev.upload_prepared_image.assert_awaited_once()

    entity = _get_entity(hass)
    image_bytes = await entity.async_image()
    assert image_bytes is not None


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
    mock_context = AsyncMock()
    mock_context.__aenter__.return_value = mock_response
    mock_session.get = MagicMock(return_value=mock_context)

    mock_upload_dev = _mock_upload_device()

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
            "homeassistant.components.opendisplay.image.prepare_image",
            return_value=FAKE_PREPARED,
        ),
        patch(
            "homeassistant.components.opendisplay.image.OpenDisplayDevice",
            return_value=mock_upload_dev,
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
        await hass.async_block_till_done()

    entity = _get_entity(hass)
    image_bytes = await entity.async_image()
    assert image_bytes is not None


async def test_upload_ble_failure_keeps_preview(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that BLE upload failure still keeps the preview image."""
    await _setup_entry(hass, mock_config_entry)

    test_image = PILImage.new("RGB", (100, 100), color="red")
    image_path = tmp_path / "test.png"
    test_image.save(image_path)

    mock_play_media = AsyncMock()
    mock_play_media.path = image_path

    mock_upload_dev = _mock_upload_device()
    mock_upload_dev.__aenter__.side_effect = BLEConnectionError("timeout")

    with (
        patch(
            "homeassistant.components.opendisplay.image.async_resolve_media",
            return_value=mock_play_media,
        ),
        patch(
            "homeassistant.components.opendisplay.image.prepare_image",
            return_value=FAKE_PREPARED,
        ),
        patch(
            "homeassistant.components.opendisplay.image.OpenDisplayDevice",
            return_value=mock_upload_dev,
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
        await hass.async_block_till_done()

    entity = _get_entity(hass)
    assert await entity.async_image() is not None
    assert "Failed to sync image" in caplog.text


async def test_upload_device_not_found_keeps_preview(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    tmp_path: Path,
) -> None:
    """Test that missing BLE device still keeps the preview and sets pending upload."""
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
            "homeassistant.components.opendisplay.image.prepare_image",
            return_value=FAKE_PREPARED,
        ),
        patch(
            "homeassistant.components.opendisplay.image.async_ble_device_from_address",
            return_value=None,
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
        await hass.async_block_till_done()

    entity = _get_entity(hass)
    assert await entity.async_image() is not None
    # Upload is queued for retry when device comes back in range
    assert entity._pending_upload is not None


async def test_image_persisted_to_disk(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmp_path: Path
) -> None:
    """Test that the processed image is persisted to disk."""
    await _setup_entry(hass, mock_config_entry)

    test_image = PILImage.new("RGB", (100, 100), color="red")
    image_path = tmp_path / "test.png"
    test_image.save(image_path)

    mock_play_media = AsyncMock()
    mock_play_media.path = image_path

    mock_upload_dev = _mock_upload_device()

    with (
        patch(
            "homeassistant.components.opendisplay.image.async_resolve_media",
            return_value=mock_play_media,
        ),
        patch(
            "homeassistant.components.opendisplay.image.prepare_image",
            return_value=FAKE_PREPARED,
        ),
        patch(
            "homeassistant.components.opendisplay.image.OpenDisplayDevice",
            return_value=mock_upload_dev,
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
        await hass.async_block_till_done()

    storage_path = _get_entity(hass)._get_storage_path()
    assert storage_path.exists()
    assert storage_path.stat().st_size > 0


async def test_extra_restore_state_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test extra_restore_state_data returns correct metadata."""
    await _setup_entry(hass, mock_config_entry)

    entity = _get_entity(hass)

    # Initially no image
    data = entity.extra_restore_state_data
    assert data.has_stored_image is False
    assert data.image_last_updated is None

    # Simulate setting an image
    entity._current_image = b"\x00"

    data = entity.extra_restore_state_data
    assert data.has_stored_image is True


def test_extra_stored_data_roundtrip() -> None:
    """Test ExtraStoredData serialization roundtrip."""
    original = OpenDisplayImageExtraStoredData(
        image_last_updated="2026-02-17T12:00:00+00:00",
        has_stored_image=True,
    )

    as_dict = original.as_dict()
    restored = OpenDisplayImageExtraStoredData.from_dict(as_dict)

    assert restored is not None
    assert restored.image_last_updated == "2026-02-17T12:00:00+00:00"
    assert restored.has_stored_image is True


def test_extra_stored_data_from_dict_invalid() -> None:
    """Test ExtraStoredData returns None for invalid data."""
    assert OpenDisplayImageExtraStoredData.from_dict({}) is None
    assert (
        OpenDisplayImageExtraStoredData.from_dict({"image_last_updated": None}) is None
    )


async def test_upload_success_clears_pending(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmp_path: Path
) -> None:
    """Test that a successful BLE upload clears _pending_upload."""
    await _setup_entry(hass, mock_config_entry)

    test_image = PILImage.new("RGB", (100, 100), color="red")
    image_path = tmp_path / "test.png"
    test_image.save(image_path)

    mock_play_media = AsyncMock()
    mock_play_media.path = image_path

    mock_upload_dev = _mock_upload_device()

    with (
        patch(
            "homeassistant.components.opendisplay.image.async_resolve_media",
            return_value=mock_play_media,
        ),
        patch(
            "homeassistant.components.opendisplay.image.prepare_image",
            return_value=FAKE_PREPARED,
        ),
        patch(
            "homeassistant.components.opendisplay.image.OpenDisplayDevice",
            return_value=mock_upload_dev,
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
        await hass.async_block_till_done()

    assert _get_entity(hass)._pending_upload is None


async def test_upload_retry_on_device_seen(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmp_path: Path
) -> None:
    """Test that a pending upload retries when the device becomes connectable."""
    await _setup_entry(hass, mock_config_entry)

    test_image = PILImage.new("RGB", (100, 100), color="red")
    image_path = tmp_path / "test.png"
    test_image.save(image_path)

    mock_play_media = AsyncMock()
    mock_play_media.path = image_path
    mock_upload_dev = _mock_upload_device()

    # First call: device not in range → _pending_upload stays set
    with (
        patch(
            "homeassistant.components.opendisplay.image.async_resolve_media",
            return_value=mock_play_media,
        ),
        patch(
            "homeassistant.components.opendisplay.image.prepare_image",
            return_value=FAKE_PREPARED,
        ),
        patch(
            "homeassistant.components.opendisplay.image.async_ble_device_from_address",
            return_value=None,
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
        await hass.async_block_till_done()

    entity = _get_entity(hass)
    assert entity._pending_upload is not None

    # Simulate the device coming back in range via Bluetooth callback
    with patch(
        "homeassistant.components.opendisplay.image.OpenDisplayDevice",
        return_value=mock_upload_dev,
    ):
        entity._async_on_device_seen(make_service_info(), BluetoothChange.ADVERTISEMENT)
        await hass.async_block_till_done()

    mock_upload_dev.upload_prepared_image.assert_awaited_once()
    assert entity._pending_upload is None


async def test_no_double_launch_while_uploading(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the BT callback does not launch a second upload while one is running."""
    await _setup_entry(hass, mock_config_entry)

    entity = _get_entity(hass)

    # Simulate a pending upload with an in-progress task
    entity._pending_upload = (FAKE_PREPARED, RefreshMode.FULL)
    running_task = MagicMock()
    running_task.done.return_value = False
    entity._upload_task = running_task

    entity._async_on_device_seen(make_service_info(), BluetoothChange.ADVERTISEMENT)

    assert entity._upload_task is running_task
