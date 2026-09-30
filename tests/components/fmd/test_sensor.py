"""Test FMD sensor entities."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.fmd.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.components.fmd.common import setup_integration


async def test_photo_count_sensor(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo count sensor."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "sensor.fmd_test_user_photo_count"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0"


async def test_photo_count_after_download(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo count updates after download."""
    from datetime import datetime

    # Mock the new device API
    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.return_value = [b"blob1", b"blob2", b"blob3"]

    # Create mock PhotoResult objects with unique data
    def create_photo_result(data: bytes):
        photo_result = MagicMock()
        photo_result.data = data
        photo_result.mime_type = "image/jpeg"
        photo_result.timestamp = datetime(2025, 1, 15, 10, 30, 0)
        photo_result.raw = {}
        return photo_result

    device_mock.decode_picture.side_effect = [
        create_photo_result(b"fake_jpeg_data_1_unique"),
        create_photo_result(b"fake_jpeg_data_2_different"),
        create_photo_result(b"fake_jpeg_data_3_another"),
    ]

    # Setup integration BEFORE patching Path methods
    await setup_integration(hass, mock_fmd_api)

    # Create mock photo objects for glob to return
    mock_photo1 = MagicMock()
    mock_photo1.name = "photo1.jpg"
    mock_photo2 = MagicMock()
    mock_photo2.name = "photo2.jpg"
    mock_photo3 = MagicMock()
    mock_photo3.name = "photo3.jpg"

    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.write_bytes"),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob") as mock_glob,
    ):
        # Use a callable for exists() that returns True for directories, False for photo files
        def exists_side_effect(self):
            return "photo_" not in str(self)

        with patch("pathlib.Path.exists", exists_side_effect):
            # glob is called by sensor's _update_media_folder_count after download
            mock_glob.return_value = [mock_photo1, mock_photo2, mock_photo3]

            # Download photos
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.fmd_test_user_photo_download"},
                blocking=True,
            )

            # Trigger sensor update
            await hass.async_block_till_done()

            state = hass.states.get("sensor.fmd_test_user_photo_count")
            assert state.state == "3"


async def test_photo_count_attributes(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo count sensor attributes."""
    from datetime import datetime

    # Mock the new device API
    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.return_value = [b"blob1", b"blob2"]

    # Create mock PhotoResult objects with unique data
    def create_photo_result(data: bytes):
        photo_result = MagicMock()
        photo_result.data = data
        photo_result.mime_type = "image/jpeg"
        photo_result.timestamp = datetime(2025, 1, 15, 10, 30, 0)
        photo_result.raw = {}
        return photo_result

    device_mock.decode_picture.side_effect = [
        create_photo_result(b"fake_jpeg_data_1_unique"),
        create_photo_result(b"fake_jpeg_data_2_different"),
    ]

    # Setup integration BEFORE patching Path methods
    await setup_integration(hass, mock_fmd_api)

    # Create mock photo objects for glob
    mock_photo1 = MagicMock()
    mock_photo2 = MagicMock()

    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.write_bytes"),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob") as mock_glob,
    ):
        # Use a callable for exists() that returns True for directories, False for photo files
        def exists_side_effect(self):
            return "photo_" not in str(self)

        with patch("pathlib.Path.exists", exists_side_effect):
            # glob returns our mock photos when sensor counts
            mock_glob.return_value = [mock_photo1, mock_photo2]

            # Download photos
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.fmd_test_user_photo_download"},
                blocking=True,
            )

            await hass.async_block_till_done()

            state = hass.states.get("sensor.fmd_test_user_photo_count")
            assert "last_download_count" in state.attributes
            assert "last_download_time" in state.attributes
            assert state.attributes["last_download_count"] == 2


async def test_photo_count_after_cleanup(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo count updates after cleanup."""
    from datetime import datetime, timedelta

    # Mock the new device API
    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.return_value = [b"blob1"]

    # Create mock PhotoResult
    photo_result = MagicMock()
    photo_result.data = b"fake_jpeg_data_unique_cleanup"
    photo_result.mime_type = "image/jpeg"
    photo_result.timestamp = datetime(2025, 1, 15, 10, 30, 0)
    photo_result.raw = {}
    device_mock.decode_picture.return_value = photo_result

    # Setup integration BEFORE patching Path methods
    await setup_integration(hass, mock_fmd_api)

    # Enable auto-cleanup
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_photo_auto_cleanup"},
        blocking=True,
    )

    # Create mock photo objects with timestamps
    old_photo = MagicMock()
    old_photo.stat.return_value.st_mtime = (
        datetime.now() - timedelta(days=8)
    ).timestamp()

    new_photo = MagicMock()
    new_photo.stat.return_value.st_mtime = datetime.now().timestamp()

    # Now patch for photo download operation
    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.write_bytes"),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob") as mock_glob,
        patch("pathlib.Path.unlink"),
    ):
        # Use a callable for exists() that returns True for directories, False for photo files
        def exists_side_effect(self):
            return "photo_" not in str(self)

        with patch("pathlib.Path.exists", exists_side_effect):
            # glob called multiple times: once to find photos to delete, once to count after
            mock_glob.side_effect = [
                [old_photo],  # First call - finds old photo to delete
                [new_photo],  # Second call - count after cleanup
            ]

            # Download photos (will trigger cleanup)
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.fmd_test_user_photo_download"},
                blocking=True,
            )
            await hass.async_block_till_done()

            state = hass.states.get("sensor.fmd_test_user_photo_count")
            assert state.state == "1"


async def test_photo_count_icon(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo count sensor icon."""
    await setup_integration(hass, mock_fmd_api)

    entity_id = "sensor.fmd_test_user_photo_count"
    state = hass.states.get(entity_id)
    assert state.attributes["icon"] == "mdi:image-multiple"


async def test_photo_count_sensor_media_folder_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo count sensor when media folder is not found."""
    # Return encrypted blobs
    mock_fmd_api.create.return_value.get_pictures.return_value = [
        "encrypted_blob_1",
    ]

    # Mock decrypt_data_blob to return base64-encoded fake image data
    import base64

    fake_image = base64.b64encode(b"fake_jpeg_data").decode("utf-8")
    mock_fmd_api.create.return_value.decrypt_data_blob.return_value = fake_image

    await setup_integration(hass, mock_fmd_api)

    # Mock Path operations - glob raises FileNotFoundError
    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.write_bytes"),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", side_effect=FileNotFoundError("Folder not found")),
    ):
        # Trigger download which will call _update_media_folder_count
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )

        await hass.async_block_till_done()

    # Sensor should have gracefully handled the error
    sensor = hass.config_entries.async_entries("fmd")[0].runtime_data.photo_count_sensor
    assert sensor._photos_in_media_folder == 0


async def test_photo_count_sensor_media_folder_permission_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo count sensor when media folder access is denied."""
    # Return encrypted blobs
    mock_fmd_api.create.return_value.get_pictures.return_value = [
        "encrypted_blob_1",
    ]

    # Mock decrypt_data_blob to return base64-encoded fake image data
    import base64

    fake_image = base64.b64encode(b"fake_jpeg_data").decode("utf-8")
    mock_fmd_api.create.return_value.decrypt_data_blob.return_value = fake_image

    await setup_integration(hass, mock_fmd_api)

    # Mock Path operations - glob raises PermissionError
    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.write_bytes"),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", side_effect=PermissionError("Access denied")),
    ):
        # Trigger download which will call _update_media_folder_count
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )

        await hass.async_block_till_done()

    # Sensor should have gracefully handled the error
    sensor = hass.config_entries.async_entries("fmd")[0].runtime_data.photo_count_sensor
    assert sensor._photos_in_media_folder == 0


async def test_photo_count_sensor_media_folder_oserror(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo count sensor when media folder access raises OSError."""
    # Return encrypted blobs
    mock_fmd_api.create.return_value.get_pictures.return_value = [
        "encrypted_blob_1",
    ]

    # Mock decrypt_data_blob to return base64-encoded fake image data
    import base64

    fake_image = base64.b64encode(b"fake_jpeg_data").decode("utf-8")
    mock_fmd_api.create.return_value.decrypt_data_blob.return_value = fake_image

    await setup_integration(hass, mock_fmd_api)

    # Mock Path operations - glob raises OSError
    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.write_bytes"),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.glob", side_effect=OSError("Drive not ready")),
    ):
        # Trigger download which will call _update_media_folder_count
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )

        await hass.async_block_till_done()

    # Sensor should have gracefully handled the error
    sensor = hass.config_entries.async_entries("fmd")[0].runtime_data.photo_count_sensor
    assert sensor._photos_in_media_folder == 0


async def test_sensor_init_invalid_date(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Test sensor initialization with invalid date string."""
    # Setup integration first to get the entry
    await setup_integration(hass, mock_fmd_api)

    # Get the entry
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    # Modify entry data to have invalid date
    new_data = dict(entry.data)
    new_data["photo_count_last_download_time"] = "invalid-date-string"
    hass.config_entries.async_update_entry(entry, data=new_data)

    # Reload the integration to trigger __init__ again
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Check that the sensor initialized with None for last_download_time
    sensor = hass.states.get("sensor.fmd_test_user_photo_count")
    assert sensor is not None
    assert sensor.attributes["last_download_time"] is None


async def test_sensor_update_media_folder_error(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Test sensor handles errors when counting media files."""
    await setup_integration(hass, mock_fmd_api)

    # Patch Path to raise exception
    with patch("homeassistant.components.fmd.sensor.Path") as mock_path_cls:
        mock_path = mock_path_cls.return_value
        mock_path.exists.return_value = True
        mock_path.is_dir.return_value = True

        # Make division return the same mock object so chaining works
        mock_path.__truediv__.return_value = mock_path

        # Raise exception when accessing glob
        mock_path.glob.side_effect = Exception("Disk error")

        # Trigger update
        sensor_entity = hass.config_entries.async_entries("fmd")[
            0
        ].runtime_data.photo_count_sensor
        sensor_entity.update_photo_count(5)

        # Verify count is 0 on error
        assert sensor_entity.native_value == 0

    # Sensor should have gracefully handled the error
    sensor = hass.config_entries.async_entries("fmd")[0].runtime_data.photo_count_sensor
    assert sensor._photos_in_media_folder == 0
