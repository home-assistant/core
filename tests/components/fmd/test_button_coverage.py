"""Test FMD button entities - additional coverage."""

import io
from unittest.mock import AsyncMock, patch

from PIL import Image

from homeassistant.core import HomeAssistant

from tests.components.fmd.common import setup_integration


async def test_button_ring_tracker_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test ring button when tracker not found."""
    await setup_integration(hass, mock_fmd_api)

    # Remove tracker from hass data
    entry = hass.config_entries.async_entries("fmd")[0]
    entry.runtime_data.tracker = None

    # Try to press ring button (should log error but not crash)
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_volume_ring_device"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_button_lock_tracker_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test lock button when tracker not found."""
    await setup_integration(hass, mock_fmd_api)

    # Remove tracker from hass data
    entry = hass.config_entries.async_entries("fmd")[0]
    entry.runtime_data.tracker = None

    # Try to press lock button (should log error but not crash)
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_lock_device"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_button_capture_front_tracker_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test capture front button when tracker not found."""
    await setup_integration(hass, mock_fmd_api)

    # Remove tracker from hass data
    entry = hass.config_entries.async_entries("fmd")[0]
    entry.runtime_data.tracker = None

    # Try to press capture front button (should log error but not crash)
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_photo_capture_front"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_button_capture_rear_tracker_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test capture rear button when tracker not found."""
    await setup_integration(hass, mock_fmd_api)

    # Remove tracker from hass data
    entry = hass.config_entries.async_entries("fmd")[0]
    entry.runtime_data.tracker = None

    # Try to press capture rear button (should log error but not crash)
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_photo_capture_rear"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_button_ring_send_command_fails(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test ring button when send_command returns False."""
    await setup_integration(hass, mock_fmd_api)

    # Make send_command return False
    api_instance = mock_fmd_api.create.return_value
    api_instance.send_command.reset_mock()
    api_instance.send_command.return_value = False

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_volume_ring_device"},
        blocking=True,
    )
    await hass.async_block_till_done()

    api_instance.send_command.assert_called_once_with("ring")


async def test_button_lock_device_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test lock button when device.lock() raises an exception."""
    await setup_integration(hass, mock_fmd_api)

    # Make device.lock() raise an exception
    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.lock.side_effect = Exception("Lock failed")

    # Press lock button - should handle error gracefully
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_lock_device"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify device.lock() was called
    device_mock.lock.assert_called_once_with(message=None)


async def test_button_capture_front_take_picture_fails(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test capture front button when take_picture returns False."""
    await setup_integration(hass, mock_fmd_api)

    # Make take_picture return False
    api_instance = mock_fmd_api.create.return_value
    api_instance.take_picture.reset_mock()
    api_instance.take_picture.return_value = False

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_photo_capture_front"},
        blocking=True,
    )
    await hass.async_block_till_done()

    api_instance.take_picture.assert_called_once_with("front")


async def test_button_capture_rear_take_picture_fails(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test capture rear button when take_picture returns False."""
    await setup_integration(hass, mock_fmd_api)

    # Make take_picture return False
    api_instance = mock_fmd_api.create.return_value
    api_instance.take_picture.reset_mock()
    api_instance.take_picture.return_value = False

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_photo_capture_rear"},
        blocking=True,
    )
    await hass.async_block_till_done()

    api_instance.take_picture.assert_called_once_with("back")


async def test_button_download_photos_sensor_not_found(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Test download photos button handles missing photo sensor gracefully."""
    # Create a simple image
    img = Image.new("RGB", (100, 100), color="green")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)

    # Mock API response
    mock_fmd_api.create.return_value.get_location.return_value = {
        "pictures": [img_bytes.getvalue()],
        "location": [],
    }

    await setup_integration(hass, mock_fmd_api)

    # Remove the photo sensor
    entry = hass.config_entries.async_entries("fmd")[0]
    entry.runtime_data.photo_count_sensor = None

    # Press the button - should not crash
    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.write_bytes"),
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )


async def test_button_download_photos_cleanup_delete_error(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Test photo cleanup handles file deletion errors gracefully."""
    await setup_integration(hass, mock_fmd_api)

    entry = hass.config_entries.async_entries("fmd")[0]

    # Enable auto-cleanup and set max to 1
    cleanup_switch = entry.runtime_data.photo_auto_cleanup_switch
    await cleanup_switch.async_turn_on()

    max_photos = entry.runtime_data.max_photos_number
    max_photos._attr_native_value = 1

    # Create two images
    img1 = Image.new("RGB", (100, 100), color="red")
    img2 = Image.new("RGB", (100, 100), color="blue")

    img1_bytes = io.BytesIO()
    img1.save(img1_bytes, format="JPEG")
    img1_bytes.seek(0)

    img2_bytes = io.BytesIO()
    img2.save(img2_bytes, format="JPEG")
    img2_bytes.seek(0)

    # Mock API response with two photos
    mock_fmd_api.create.return_value.get_location.return_value = {
        "pictures": [img1_bytes.getvalue(), img2_bytes.getvalue()],
        "location": [],
    }

    # Mock Path.unlink to raise exception
    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.write_bytes"),
        patch("pathlib.Path.unlink", side_effect=Exception("Permission denied")),
    ):
        # Press the button - should handle error
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )


async def test_button_wipe_device_success(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Test wipe device button successfully calls device.wipe()."""
    await setup_integration(hass, mock_fmd_api)

    entry = hass.config_entries.async_entries("fmd")[0]

    # Enable wipe safety
    safety_switch = entry.runtime_data.wipe_safety_switch
    await safety_switch.async_turn_on()

    # Get the wipe PIN from the text entity
    wipe_pin_text = entry.runtime_data.wipe_pin_text
    await wipe_pin_text.async_set_value("1234")

    # Mock device.wipe()
    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.wipe = AsyncMock()

    # Press the wipe button
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_wipe_execute"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify device.wipe() was called with correct parameters
    device_mock.wipe.assert_called_once_with(pin="1234", confirm=True)

    # Safety switch should be automatically disabled
    assert safety_switch.is_on is False


async def test_download_photos_no_tracker(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Download Photos button returns early if tracker missing."""
    await setup_integration(hass, mock_fmd_api)

    # Remove tracker
    hass.config_entries.async_entries("fmd")[0].runtime_data.tracker = None

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_photo_download"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_download_photos_missing_max_photos_number(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Download Photos button returns early if max_photos_number missing."""
    await setup_integration(hass, mock_fmd_api)

    # Remove max_photos_number entity reference
    hass.config_entries.async_entries("fmd")[0].runtime_data.max_photos_number = None

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_photo_download"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_download_photos_no_pictures(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Download Photos button handles empty picture list."""
    # Ensure no pictures returned from device.get_picture_blobs
    device = mock_fmd_api.create.return_value.device.return_value
    device.get_picture_blobs.return_value = []

    await setup_integration(hass, mock_fmd_api)

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_photo_download"},
        blocking=True,
    )
    await hass.async_block_till_done()
    device.get_picture_blobs.assert_called()


async def test_download_photos_media_dir_creation_failure(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Download Photos button handles media directory creation failure."""
    import base64
    from unittest.mock import patch

    # Return one fake picture to reach dir creation
    mock_fmd_api.create.return_value.get_pictures.return_value = [
        base64.b64encode(b"fake_image").decode()
    ]
    mock_fmd_api.create.return_value.decrypt_data_blob.return_value = base64.b64encode(
        b"jpeg_data"
    ).decode()

    await setup_integration(hass, mock_fmd_api)

    # Force mkdir to fail
    with patch("pathlib.Path.mkdir", side_effect=OSError("mkdir fail")):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )
        await hass.async_block_till_done()


async def test_download_photos_exif_timestamp_filename(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
    tmp_path,
) -> None:
    """Ensure EXIF timestamp is used in filename when present."""
    from unittest.mock import MagicMock

    # Configure device.get_picture_blobs to return one blob
    device = mock_fmd_api.create.return_value.device.return_value
    device.get_picture_blobs.return_value = [b"blob_data"]

    # Configure decode_picture to return PhotoResult
    photo_result = MagicMock()
    photo_result.data = b"jpeg_bytes"
    photo_result.mime_type = "image/jpeg"
    photo_result.timestamp = None  # No timestamp, will use EXIF
    photo_result.raw = {}
    device.decode_picture.return_value = photo_result

    # Mock executor to actually run sync functions
    async def mock_executor_job(func, *args):
        return func(*args)

    # Setup integration first
    await setup_integration(hass, mock_fmd_api)

    # Force using config/media by making /media path construction return a fake path
    # that doesn't exist, so the code falls back to hass.config.path("media")
    from pathlib import Path as RealPath

    def path_constructor(path_str):
        """Custom Path constructor that returns a non-existent path for /media."""
        if path_str == "/media":
            # Return a Path that doesn't exist and isn't a directory
            return RealPath("/nonexistent_media_path")
        return RealPath(path_str)

    # Patch media base to a temporary directory; patch Path in the fmd.button module
    with (
        patch.object(hass, "async_add_executor_job", side_effect=mock_executor_job),
        patch("homeassistant.components.fmd.button.Path", side_effect=path_constructor),
        patch.object(hass.config, "path", return_value=str(tmp_path)),
    ):
        # Patch PIL Image.open to yield EXIF DateTimeOriginal
        class DummyImg:
            def getexif(self):
                return {36867: "2025:10:19 15:00:34"}

        with patch("PIL.Image.open", return_value=DummyImg()):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.fmd_test_user_photo_download"},
                blocking=True,
            )
            await hass.async_block_till_done()

    # Verify file with expected timestamp exists
    device_dir = tmp_path / "fmd" / "test_user"
    # Debug: check if directory was created
    assert device_dir.exists(), f"Device directory not created: {device_dir}"
    all_files = list(device_dir.glob("*.jpg"))
    assert all_files, f"No JPG files found in {device_dir}"
    files = list(device_dir.glob("photo_20251019_150034_*.jpg"))
    assert files, (
        f"Expected a photo file with EXIF timestamp in name. Found: {[f.name for f in all_files]}"
    )


async def test_download_photos_duplicate_skip(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
    tmp_path,
) -> None:
    """Existing photo with same hash should be skipped (duplicate)."""
    import base64
    import hashlib

    image_bytes = b"same_image_content"
    decrypted = base64.b64encode(image_bytes).decode()
    mock_fmd_api.create.return_value.get_pictures.return_value = [
        base64.b64encode(image_bytes).decode()
    ]
    mock_fmd_api.create.return_value.decrypt_data_blob.return_value = decrypted

    # Use tmp media path and no EXIF
    with (
        patch.object(hass.config, "path", return_value=str(tmp_path)),
        patch("PIL.Image.open", side_effect=Exception("no exif")),
    ):
        await setup_integration(hass, mock_fmd_api)

        # Pre-create duplicate file using same content hash
        h = hashlib.sha256(image_bytes).hexdigest()[:8]
        device_dir = tmp_path / "fmd" / "test_user"
        device_dir.mkdir(parents=True, exist_ok=True)
        pre_file = device_dir / f"photo_{h}.jpg"
        pre_file.write_bytes(image_bytes)

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )
        await hass.async_block_till_done()

    # Still only one file present
    files = list((tmp_path / "fmd" / "test_user").glob("*.jpg"))
    assert len(files) == 1
