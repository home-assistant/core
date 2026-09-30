"""Test FMD photo download button entities."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import io
import logging
import os
from pathlib import Path
import time
from unittest.mock import AsyncMock, MagicMock, patch

from fmd_api import AuthenticationError, FmdApiException, OperationError
from PIL import Image
import pytest

from homeassistant.components.fmd.button import FmdDownloadPhotosButton
from homeassistant.components.fmd.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.components.fmd.common import setup_integration


async def test_download_photos_button(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test download photos button with new picture API (fmd_api 2.0.4+)."""
    # Mock device() to return the mock device with get_picture_blobs
    mock_device = mock_fmd_api.create.return_value.device.return_value

    # Return two picture blobs
    mock_device.get_picture_blobs.return_value = [
        "encrypted_blob_1",
        "encrypted_blob_2",
    ]

    # Mock decode_picture to return PhotoResult with unique data
    def make_photo_result(data: bytes):
        result = MagicMock()
        result.data = data
        result.mime_type = "image/jpeg"
        result.timestamp = datetime(2025, 10, 23, 12, 0, 0)
        result.raw = {}
        return result

    mock_device.decode_picture.side_effect = [
        make_photo_result(b"fake_jpeg_data_1_unique"),
        make_photo_result(b"fake_jpeg_data_2_different"),
    ]

    # Setup integration BEFORE patching Path methods
    await setup_integration(hass, mock_fmd_api)

    # Use a callable for exists() to handle any number of calls
    # Returns True for directories, False for photo files
    def exists_side_effect(self):
        return "photo_" not in str(self)

    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.exists", exists_side_effect),
        patch("pathlib.Path.write_bytes") as mock_write,
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )

        # Verify get_picture_blobs was called on device
        mock_device.get_picture_blobs.assert_called_once()
        # Verify 2 photos were decoded
        assert mock_device.decode_picture.call_count == 2
        # Verify 2 photos were written
        assert mock_write.call_count == 2


async def test_download_photos_with_cleanup(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test download photos with auto-cleanup enabled."""
    # Mock device() to return the mock device
    mock_device = mock_fmd_api.create.return_value.device.return_value

    # Return one picture blob
    mock_device.get_picture_blobs.return_value = ["encrypted_blob_1"]

    # Mock decode_picture to return PhotoResult
    photo_result = MagicMock()
    photo_result.data = b"fake_jpeg_data_cleanup_test"
    photo_result.mime_type = "image/jpeg"
    photo_result.timestamp = datetime(2025, 10, 23, 12, 0, 0)
    photo_result.raw = {}
    mock_device.decode_picture.return_value = photo_result

    # Setup integration BEFORE patching Path methods
    await setup_integration(hass, mock_fmd_api)

    # Set max photos to 3
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.fmd_test_user_photo_max_to_retain", "value": 3},
        blocking=True,
    )

    # Enable auto-cleanup
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_photo_auto_cleanup"},
        blocking=True,
    )

    # Create mock old photos (4 old photos + will add 1 new = 5 total,
    # limit is 3, so 2 should be deleted)
    old_photos = []
    for i in range(4):
        photo = MagicMock()
        photo.stat.return_value.st_mtime = (
            datetime.now() - timedelta(days=i + 1)
        ).timestamp()
        photo.name = f"old_photo_{i}.jpg"
        old_photos.append(photo)

    # The new photo that will be downloaded
    new_photo = MagicMock()
    new_photo.stat.return_value.st_mtime = datetime.now().timestamp()
    new_photo.name = "new_photo.jpg"

    # Use a callable for exists() that returns True for directories, False for photo files
    def exists_side_effect(self):
        return "photo_" not in str(self)

    # Now patch only for the photo download operation
    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.write_bytes"),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.exists", exists_side_effect),
        patch("pathlib.Path.glob") as mock_glob,
    ):
        # glob returns all photos (4 old + 1 new = 5) when cleanup runs
        mock_glob.return_value = old_photos + [new_photo]

        # Mock async_add_executor_job to actually execute the callable
        async def mock_executor_job(func, *args):
            return func(*args)

        with patch.object(
            hass, "async_add_executor_job", side_effect=mock_executor_job
        ):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.fmd_test_user_photo_download"},
                blocking=True,
            )

            # Verify the 2 oldest photos were deleted
            old_photos[3].unlink.assert_called_once()
            old_photos[2].unlink.assert_called_once()
            # Ensure photos 0 and 1 were NOT deleted (they are newer)
            old_photos[0].unlink.assert_not_called()
            old_photos[1].unlink.assert_not_called()


async def test_download_photos_empty_result(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test download photos button with empty result."""
    await setup_integration(hass, mock_fmd_api)

    # Return empty list
    mock_fmd_api.create.return_value.get_pictures.return_value = []

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_photo_download"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Sensor should have count of 0
    sensor = hass.config_entries.async_entries("fmd")[0].runtime_data.photo_count_sensor
    assert sensor._last_download_count == 0


async def test_download_photos_cleanup_noop_no_warnings(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
    caplog,
) -> None:
    """No cleanup warnings should be logged when count <= max_to_retain."""
    import base64

    mock_fmd_api.create.return_value.get_pictures.return_value = [
        base64.b64encode(b"jpeg_data").decode()
    ]
    mock_fmd_api.create.return_value.decrypt_data_blob.return_value = base64.b64encode(
        b"jpeg_data"
    ).decode()

    await setup_integration(hass, mock_fmd_api)

    # Set retention higher than existing count
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.fmd_test_user_photo_max_to_retain", "value": 5},
        blocking=True,
    )
    # Enable auto-cleanup
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.fmd_test_user_photo_auto_cleanup"},
        blocking=True,
    )

    photos = [MagicMock(), MagicMock()]

    def exists_side_effect(self):
        return "photo_" not in str(self)

    caplog.clear()
    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.write_bytes"),
        patch(
            "pathlib.Path.is_dir",
            return_value=True,
        ),
        patch("pathlib.Path.exists", exists_side_effect),
        patch(
            "pathlib.Path.glob",
            return_value=photos,
        ),
    ):

        async def mock_executor_job(func, *args):
            return func(*args)

        with patch.object(
            hass, "async_add_executor_job", side_effect=mock_executor_job
        ):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.fmd_test_user_photo_download"},
                blocking=True,
            )
            await hass.async_block_till_done()

    # Ensure no AUTO-CLEANUP warning entries present
    assert not any(
        "AUTO-CLEANUP" in r.getMessage() and r.levelname == "WARNING"
        for r in caplog.records
    )


async def test_download_photos_exif_present_but_no_timestamp_tags(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
    tmp_path,
) -> None:
    """With EXIF present but no datetime tags, fallback filename used."""

    # Setup integration first
    await setup_integration(hass, mock_fmd_api)

    # Mock new API
    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.return_value = [b"encrypted_photo"]

    photo_result = MagicMock()
    photo_result.data = b"img_no_tags"
    photo_result.mime_type = "image/jpeg"
    photo_result.timestamp = None  # No timestamp
    photo_result.raw = {}
    device_mock.decode_picture.return_value = photo_result

    # Make hass.config.path return tmp dir
    with patch.object(hass.config, "path", return_value=str(tmp_path)):
        # Mock /media path doesn't exist
        with patch("pathlib.Path.is_dir") as mock_is_dir:
            # /media doesn't exist, so config/media is used
            mock_is_dir.return_value = False

            # Mock Path.mkdir and write_bytes
            with (
                patch("pathlib.Path.mkdir"),
                patch("pathlib.Path.exists", return_value=False),
                patch("pathlib.Path.write_bytes"),
            ):

                class DummyImg:
                    def getexif(self):
                        # EXIF present but no datetime tags
                        return {1234: "something"}

                with patch("PIL.Image.open", return_value=DummyImg()):
                    await hass.services.async_call(
                        "button",
                        "press",
                        {"entity_id": "button.fmd_test_user_photo_download"},
                        blocking=True,
                    )
                    await hass.async_block_till_done()

    # Verify API calls were made
    device_mock.get_picture_blobs.assert_called()
    device_mock.decode_picture.assert_called()


async def test_download_photos_decode_failure(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo download handles decode failure for one photo."""
    await setup_integration(hass, mock_fmd_api)

    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.return_value = [b"blob1", b"blob2"]

    # First decode succeeds, second fails
    photo_result1 = MagicMock()
    photo_result1.data = b"img1"
    photo_result1.mime_type = "image/jpeg"
    photo_result1.timestamp = None
    photo_result1.raw = {}

    device_mock.decode_picture.side_effect = [photo_result1, Exception("decode failed")]

    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.write_bytes"),
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )
        await hass.async_block_till_done()

    # Should have attempted to decode both
    assert device_mock.decode_picture.call_count == 2


async def test_download_photos_sensor_update_fallback(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo download when photo count sensor is missing."""
    await setup_integration(hass, mock_fmd_api)

    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.return_value = [b"encrypted_photo"]

    photo_result = MagicMock()
    photo_result.data = b"img_data"
    photo_result.mime_type = "image/jpeg"
    photo_result.timestamp = None
    photo_result.raw = {}
    device_mock.decode_picture.return_value = photo_result

    # Remove photo_count_sensor from runtime data
    entry = hass.config_entries.async_entries("fmd")[0]
    entry.runtime_data.photo_count_sensor = None

    with (
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.write_bytes"),
    ):
        # Should not raise, just skip sensor update
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )
        await hass.async_block_till_done()

    device_mock.get_picture_blobs.assert_called()


async def test_download_photos_media_directory_creation_failure(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test download photos button handles media directory creation failure."""
    await setup_integration(hass, mock_fmd_api)

    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.return_value = [b"encrypted_photo"]

    photo_result = MagicMock()
    photo_result.data = b"img_data"
    photo_result.mime_type = "image/jpeg"
    photo_result.timestamp = None
    photo_result.raw = {}
    device_mock.decode_picture.return_value = photo_result

    # Mock Path.mkdir to raise OSError
    with (
        patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")),
        patch("pathlib.Path.is_dir", return_value=True),
    ):
        # Should not raise, just return early after directory creation failure
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )
        await hass.async_block_till_done()

    # Should have attempted to get pictures but not decode since directory creation failed
    device_mock.get_picture_blobs.assert_called_once()
    device_mock.decode_picture.assert_not_called()


async def test_download_photos_duplicate_detection(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Second identical photo is skipped as duplicate (exists())."""
    await setup_integration(hass, mock_fmd_api)
    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.return_value = [b"blob1", b"blob2"]

    # Two PhotoResults with identical data -> same hash
    pr1 = MagicMock()
    pr1.data = b"IDENTICAL_DATA"
    pr1.mime_type = "image/jpeg"
    pr1.timestamp = None
    pr1.raw = {}
    pr2 = MagicMock()
    pr2.data = b"IDENTICAL_DATA"
    pr2.mime_type = "image/jpeg"
    pr2.timestamp = None
    pr2.raw = {}
    device_mock.decode_picture.side_effect = [pr1, pr2]

    # exists() should return False for first file creation, True for second (duplicate)
    first_call = {"done": False}

    def exists_side_effect(self):
        # Directories -> True, files containing photo_ -> first False then True
        if "photo_" not in str(self):
            return True
        if not first_call["done"]:
            first_call["done"] = True
            return False
        return True

    with (
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.exists", exists_side_effect),
        patch("pathlib.Path.write_bytes") as mock_write,
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )

    # Only first photo written
    assert mock_write.call_count == 1


async def test_download_photos_exif_open_failure(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """EXIF extraction failure (Image.open raises) uses hash-only filename path."""
    await setup_integration(hass, mock_fmd_api)
    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.return_value = [b"blob1"]
    pr = MagicMock()
    pr.data = b"NO_EXIF_IMAGE"
    pr.mime_type = "image/jpeg"
    pr.timestamp = None
    pr.raw = {}
    device_mock.decode_picture.return_value = pr

    with (
        patch("PIL.Image.open", side_effect=RuntimeError("exif boom")),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.write_bytes") as mock_write,
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )

    # File written despite EXIF failure
    assert mock_write.call_count == 1


async def test_download_photos_exif_datetimeoriginal_used_first(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """When EXIF has DateTimeOriginal (36867), it's used and other tags ignored."""
    await setup_integration(hass, mock_fmd_api)

    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.return_value = [b"blob1"]

    pr = MagicMock()
    pr.data = b"IMG_WITH_EXIF"
    pr.mime_type = "image/jpeg"
    pr.timestamp = None  # Force EXIF fallback
    pr.raw = {}
    device_mock.decode_picture.return_value = pr

    # Create mock image with EXIF containing DateTimeOriginal (36867)
    class MockImg:
        def getexif(self):
            # Include all three tags - DateTimeOriginal should be preferred
            return {
                36867: "2025:01:15 10:30:45",  # DateTimeOriginal
                36868: "2025:01:16 11:00:00",  # DateTimeDigitized
                306: "2025:01:17 12:00:00",  # DateTime
            }

    with (
        patch("PIL.Image.open", return_value=MockImg()),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.write_bytes") as mock_write,
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )

    # Verify file was written (EXIF timestamp extraction logged)
    assert mock_write.call_count == 1


async def test_download_photos_exif_digitized_when_original_missing(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """When DateTimeOriginal absent but DateTimeDigitized present, use it."""
    await setup_integration(hass, mock_fmd_api)

    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.return_value = [b"blob1"]

    pr = MagicMock()
    pr.data = b"IMG_DIGITIZED"
    pr.mime_type = "image/jpeg"
    pr.timestamp = None
    pr.raw = {}
    device_mock.decode_picture.return_value = pr

    class MockImg:
        def getexif(self):
            # Only DateTimeDigitized and DateTime present
            return {
                36868: "2025:02:20 14:15:30",
                306: "2025:02:21 15:00:00",
            }

    with (
        patch("PIL.Image.open", return_value=MockImg()),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.write_bytes") as mock_write,
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )

    # Verify file was written (EXIF timestamp extraction logged)
    assert mock_write.call_count == 1


async def test_download_photos_exif_datetime_fallback(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """When only DateTime (306) present, use it as last resort."""
    await setup_integration(hass, mock_fmd_api)

    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.return_value = [b"blob1"]

    pr = MagicMock()
    pr.data = b"IMG_DATETIME_ONLY"
    pr.mime_type = "image/jpeg"
    pr.timestamp = None
    pr.raw = {}
    device_mock.decode_picture.return_value = pr

    class MockImg:
        def getexif(self):
            # Only DateTime tag
            return {306: "2025:03:10 09:45:12"}

    with (
        patch("PIL.Image.open", return_value=MockImg()),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.write_bytes") as mock_write,
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )

    # Verify file was written (EXIF timestamp extraction logged)
    assert mock_write.call_count == 1


async def test_download_photos_exif_with_whitespace_and_nulls(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """EXIF datetime value with whitespace and null bytes is cleaned."""
    await setup_integration(hass, mock_fmd_api)

    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.return_value = [b"blob1"]

    pr = MagicMock()
    pr.data = b"IMG_DIRTY_EXIF"
    pr.mime_type = "image/jpeg"
    pr.timestamp = None
    pr.raw = {}
    device_mock.decode_picture.return_value = pr

    class MockImg:
        def getexif(self):
            # DateTime with extra whitespace and null bytes
            return {36867: "  2025:04:05 16:20:30\x00\x00  "}

    with (
        patch("PIL.Image.open", return_value=MockImg()),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("pathlib.Path.mkdir"),
        patch("pathlib.Path.exists", return_value=False),
        patch("pathlib.Path.write_bytes") as mock_write,
    ):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )

    # Verify file was written (EXIF timestamp extraction logged)
    assert mock_write.call_count == 1


async def test_cleanup_old_photos_deletes_oldest(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, tmp_path: Path
) -> None:
    """Cleanup should delete oldest photos when count exceeds the limit."""
    await setup_integration(hass, mock_fmd_api)

    # Prepare a fake media directory under hass config path
    entry = hass.config_entries.async_entries("fmd")[0]

    # Use hass.config.path('media') base and create fmd subdir
    media_dir = (
        Path(hass.config.path("media"))
        / "fmd"
        / entry.runtime_data.device_info["name"].split()[1]
    )
    media_dir.mkdir(parents=True, exist_ok=True)

    # Clean up any existing jpg files that may have been created by other tests
    for existing in media_dir.glob("*.jpg"):
        existing.unlink()

    # Create 4 dummy photo files with increasing modification times
    files = []
    for i in range(4):
        f = media_dir / f"photo_old_{i}.jpg"
        f.write_bytes(b"testdata%d" % i)
        # Set mtime progressively older
        ts = time.time() - (100 * (4 - i))
        os.utime(f, (ts, ts))
        files.append(f)

    # Create a button instance to call cleanup directly
    # Construct a fake entry object to pass to button
    mock_entry = hass.config_entries.async_entries(domain=DOMAIN)[0]
    button = FmdDownloadPhotosButton(hass, mock_entry)

    # Now call the cleanup to retain only 2 files
    await button._cleanup_old_photos(media_dir, 2)

    # Only 2 files should remain
    remaining = sorted(p.name for p in media_dir.glob("*.jpg"))
    assert len(remaining) == 2

    # Ensure the two newest remain (highest indices in our create loop)
    assert "photo_old_3.jpg" in remaining
    assert "photo_old_2.jpg" in remaining


@pytest.mark.parametrize(
    "exc_cls, msg_contains",
    [
        (AuthenticationError, "Authentication failed"),
        (OperationError, "Photo download command failed"),
        (FmdApiException, "Photo download command failed"),
    ],
)
async def test_download_photos_outer_known_errors(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, exc_cls, msg_contains
) -> None:
    """device.get_picture_blobs raising specific exceptions maps to HomeAssistantError paths."""
    await setup_integration(hass, mock_fmd_api)
    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.side_effect = exc_cls("boom")

    with pytest.raises(HomeAssistantError, match=msg_contains):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )


async def test_download_photos_outer_generic_error(
    hass: HomeAssistant, mock_fmd_api: AsyncMock
) -> None:
    """Generic unexpected exception path maps to HomeAssistantError."""
    await setup_integration(hass, mock_fmd_api)
    device_mock = mock_fmd_api.create.return_value.device.return_value
    device_mock.get_picture_blobs.side_effect = RuntimeError("unexpected")

    with pytest.raises(HomeAssistantError, match="Photo download command failed"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.fmd_test_user_photo_download"},
            blocking=True,
        )


async def test_download_photos_cleanup_error(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test photo cleanup logs error when deletion fails."""
    await setup_integration(hass, mock_fmd_api)

    # Mock the switch entity to return True for is_on
    mock_switch = MagicMock()
    mock_switch.is_on = True
    hass.config_entries.async_entries("fmd")[0].runtime_data.photo_auto_cleanup_switch = mock_switch

    # Mock max photos number to 1 so we trigger cleanup with 2 photos
    mock_number = MagicMock()
    mock_number.native_value = 1
    hass.config_entries.async_entries("fmd")[0].runtime_data.max_photos_number = mock_number

    # Mock Device to return blobs
    with patch("homeassistant.components.fmd.button.Device") as mock_device_cls:
        mock_device = mock_device_cls.return_value
        mock_device.get_picture_blobs = AsyncMock(return_value=[b"1", b"2"])

        mock_photo_result = MagicMock()
        mock_photo_result.data = b"image_data"
        mock_photo_result.mime_type = "image/jpeg"
        mock_photo_result.timestamp = None
        mock_device.decode_picture = AsyncMock(return_value=mock_photo_result)

        # Mock Path
        with patch("homeassistant.components.fmd.button.Path") as mock_path_cls:
            mock_base = MagicMock()
            mock_base.exists.return_value = True
            mock_base.is_dir.return_value = True
            mock_path_cls.return_value = mock_base

            mock_fmd = MagicMock()
            mock_base.__truediv__.return_value = mock_fmd

            mock_media_dir = MagicMock()
            mock_fmd.__truediv__.return_value = mock_media_dir

            # Create mock photos
            mock_photo1 = MagicMock()
            mock_photo1.stat.return_value.st_mtime = 100
            mock_photo1.name = "photo1.jpg"
            # unlink raises exception
            mock_photo1.unlink.side_effect = Exception("Delete failed")

            mock_photo2 = MagicMock()
            mock_photo2.stat.return_value.st_mtime = 200
            mock_photo2.name = "photo2.jpg"

            # glob returns list of photos
            mock_media_dir.glob.return_value = [mock_photo1, mock_photo2]

            # Trigger download
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.fmd_test_user_photo_download"},
                blocking=True,
            )

            # Verify error log
            assert "Failed to delete photo photo1.jpg: Delete failed" in caplog.text


async def test_download_photos_cleanup_outer_error(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test photo cleanup handles outer exception (e.g. glob failure)."""
    await setup_integration(hass, mock_fmd_api)

    # Mock the switch entity to return True for is_on
    mock_switch = MagicMock()
    mock_switch.is_on = True
    hass.config_entries.async_entries("fmd")[0].runtime_data.photo_auto_cleanup_switch = mock_switch

    # Mock max photos number
    mock_number = MagicMock()
    mock_number.native_value = 1
    hass.config_entries.async_entries("fmd")[0].runtime_data.max_photos_number = mock_number

    # Mock Device to return blobs
    with patch("homeassistant.components.fmd.button.Device") as mock_device_cls:
        mock_device = mock_device_cls.return_value
        mock_device.get_picture_blobs = AsyncMock(return_value=[b"1"])
        mock_device.decode_picture = AsyncMock(
            return_value=MagicMock(data=b"img", mime_type="image/jpeg", timestamp=None)
        )

        # Mock Path
        with patch("homeassistant.components.fmd.button.Path") as mock_path_cls:
            mock_base = MagicMock()
            mock_base.exists.return_value = True
            mock_base.is_dir.return_value = True
            mock_path_cls.return_value = mock_base

            mock_fmd = MagicMock()
            mock_base.__truediv__.return_value = mock_fmd

            mock_media_dir = MagicMock()
            mock_fmd.__truediv__.return_value = mock_media_dir

            # glob raises exception
            mock_media_dir.glob.side_effect = Exception("Glob failed")

            # Trigger download
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.fmd_test_user_photo_download"},
                blocking=True,
            )

            # Verify error log
            assert "Error during photo cleanup: Glob failed" in caplog.text


async def test_photo_download_button_image_processing_success(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo download with valid image and fallback to EXIF (timestamp None)."""
    # Create a fake JPEG image (EXIF path will be attempted because timestamp=None)
    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)
    raw_bytes = img_bytes.getvalue()

    device = mock_fmd_api.create.return_value.device.return_value
    device.get_picture_blobs.return_value = [b"blob1"]

    # Return PhotoResult-like object with timestamp=None to force EXIF path
    photo_result = MagicMock()
    photo_result.data = raw_bytes
    photo_result.mime_type = "image/jpeg"
    photo_result.timestamp = None  # Force EXIF extraction code path
    photo_result.raw = {}
    device.decode_picture.return_value = photo_result

    await setup_integration(hass, mock_fmd_api)

    with patch("pathlib.Path.mkdir"):
        with patch("pathlib.Path.exists", return_value=True):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.fmd_test_user_photo_download"},
                blocking=True,
            )
            await hass.async_block_till_done()

    device.get_picture_blobs.assert_called()


async def test_photo_download_button_image_no_exif(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo download with image that has no EXIF data (still saved)."""
    img = Image.new("RGB", (100, 100), color="blue")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)
    raw_bytes = img_bytes.getvalue()

    device = mock_fmd_api.create.return_value.device.return_value
    device.get_picture_blobs.return_value = [b"blob1"]

    photo_result = MagicMock()
    photo_result.data = raw_bytes
    photo_result.mime_type = "image/jpeg"
    photo_result.timestamp = None  # triggers EXIF attempt -> none found
    photo_result.raw = {}
    device.decode_picture.return_value = photo_result

    await setup_integration(hass, mock_fmd_api)

    with patch("pathlib.Path.mkdir"):
        with patch("pathlib.Path.exists", return_value=True):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.fmd_test_user_photo_download"},
                blocking=True,
            )
            await hass.async_block_till_done()

    device.get_picture_blobs.assert_called()


async def test_photo_download_button_invalid_image_data(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo download with invalid image data (decode succeeds, EXIF fails)."""
    device = mock_fmd_api.create.return_value.device.return_value
    device.get_picture_blobs.return_value = [b"blob1"]

    # Corrupted bytes that PIL cannot parse as JPEG
    photo_result = MagicMock()
    photo_result.data = b"not_a_real_image"
    photo_result.mime_type = "image/jpeg"
    photo_result.timestamp = None
    photo_result.raw = {}
    device.decode_picture.return_value = photo_result

    await setup_integration(hass, mock_fmd_api)

    with patch("pathlib.Path.mkdir"):
        with patch("pathlib.Path.exists", return_value=True):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.fmd_test_user_photo_download"},
                blocking=True,
            )
            await hass.async_block_till_done()

    device.get_picture_blobs.assert_called()


async def test_photo_download_max_photos_not_found(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo download when max_photos_number entity not found (no API call)."""
    await setup_integration(hass, mock_fmd_api)

    entry = hass.config_entries.async_entries("fmd")[0]
    entry.runtime_data.max_photos_number = None

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.fmd_test_user_photo_download"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_fmd_api.create.return_value.device.return_value.get_picture_blobs.assert_not_called()


async def test_photo_download_media_fallback_path(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo download uses fallback media path when /media doesn't exist."""
    img = Image.new("RGB", (100, 100), color="green")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)
    raw_bytes = img_bytes.getvalue()

    device = mock_fmd_api.create.return_value.device.return_value
    device.get_picture_blobs.return_value = [b"blob1"]
    photo_result = MagicMock()
    photo_result.data = raw_bytes
    photo_result.mime_type = "image/jpeg"
    photo_result.timestamp = None
    photo_result.raw = {}
    device.decode_picture.return_value = photo_result

    await setup_integration(hass, mock_fmd_api)

    with patch("pathlib.Path.mkdir"):
        with patch("pathlib.Path.exists", return_value=False):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.fmd_test_user_photo_download"},
                blocking=True,
            )
            await hass.async_block_till_done()

    device.get_picture_blobs.assert_called()


async def test_photo_download_multiple_photos(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test photo download with multiple blobs decoded sequentially."""
    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes.seek(0)
    raw_bytes = img_bytes.getvalue()

    device = mock_fmd_api.create.return_value.device.return_value
    device.get_picture_blobs.return_value = [b"blob1", b"blob2", b"blob3"]

    # Use side_effect to return a new PhotoResult for each blob
    def mk_photo_result():
        pr = MagicMock()
        pr.data = raw_bytes
        pr.mime_type = "image/jpeg"
        pr.timestamp = None  # exercise EXIF path each time
        pr.raw = {}
        return pr

    device.decode_picture.side_effect = [
        mk_photo_result(),
        mk_photo_result(),
        mk_photo_result(),
    ]

    await setup_integration(hass, mock_fmd_api)

    with patch("pathlib.Path.mkdir"):
        with patch("pathlib.Path.exists", return_value=True):
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.fmd_test_user_photo_download"},
                blocking=True,
            )
            await hass.async_block_till_done()

    device.get_picture_blobs.assert_called()


async def test_download_photos_duplicate_skipped(
    hass: HomeAssistant, mock_fmd_api, tmp_path: Path
) -> None:
    """If a photo file already exists, it should be skipped (no write)."""
    device = mock_fmd_api.create.return_value.device.return_value
    device.get_picture_blobs.return_value = [b"blob1"]

    # Deterministic timestamp so we can pre-create duplicate
    photo_bytes = b"duplicate_test_bytes"
    photo_result = MagicMock()
    photo_result.data = photo_bytes
    photo_result.mime_type = "image/jpeg"
    photo_result.timestamp = datetime(2025, 1, 1, 0, 0, 0)
    photo_result.raw = {}
    device.decode_picture.return_value = photo_result

    # Pre-create the expected filename
    content_hash = hashlib.sha256(photo_bytes).hexdigest()[:8]
    expected_filename = f"photo_20250101_000000_{content_hash}.jpg"

    await setup_integration(hass, mock_fmd_api)

    with patch.object(hass.config, "path", return_value=str(tmp_path)):
        with patch("pathlib.Path.is_dir", return_value=False):
            media_dir = tmp_path / "fmd" / "test_user"
            media_dir.mkdir(parents=True, exist_ok=True)
            (media_dir / expected_filename).write_bytes(b"already_here")

            with patch("pathlib.Path.write_bytes") as mock_write:
                await hass.services.async_call(
                    "button",
                    "press",
                    {"entity_id": "button.fmd_test_user_photo_download"},
                    blocking=True,
                )
                mock_write.assert_not_called()


async def test_download_photos_no_photos_found(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog
) -> None:
    """When no pictures are found, warn and return."""
    caplog.set_level(logging.WARNING)
    await setup_integration(hass, mock_fmd_api)

    btn = FmdDownloadPhotosButton(
        hass, hass.config_entries.async_entries(domain=DOMAIN)[0]
    )

    mock_device = mock_fmd_api.create.return_value.device.return_value
    mock_device.get_picture_blobs.return_value = []

    await btn.async_press()

    assert any("No photos found on server" in rec.message for rec in caplog.records)


async def test_download_photos_mkdir_failure_logs_error(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog, tmp_path: Path
) -> None:
    """If media directory cannot be created, log an error and stop."""
    caplog.set_level(logging.ERROR)
    await setup_integration(hass, mock_fmd_api)

    btn = FmdDownloadPhotosButton(
        hass, hass.config_entries.async_entries(domain=DOMAIN)[0]
    )

    mock_device = mock_fmd_api.create.return_value.device.return_value
    mock_device.get_picture_blobs.return_value = [b"blob1"]

    # Patch Path.mkdir to raise an exception
    with patch("pathlib.Path.mkdir", side_effect=Exception("fail mkdir")):
        await btn.async_press()

    assert any(
        "Failed to create media directory" in rec.message for rec in caplog.records
    )


async def test_download_photos_exif_extraction_failure_logs_warning(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog: MagicMock
) -> None:
    """If EXIF extraction fails, log a warning and continue."""
    caplog.set_level(logging.WARNING)
    await setup_integration(hass, mock_fmd_api)

    # Ensure media dir exists
    media_dir = (
        Path(hass.config.path("media"))
        / "fmd"
        / hass.config_entries.async_entries("fmd")[0]
        .runtime_data.device_info["name"]
        .split()[1]
    )
    media_dir.mkdir(parents=True, exist_ok=True)
    # Ensure isolation: remove any leftover photo files from previous tests
    for existing in media_dir.glob("*.jpg"):
        existing.unlink()

    btn = FmdDownloadPhotosButton(
        hass, hass.config_entries.async_entries(domain=DOMAIN)[0]
    )

    mock_device = mock_fmd_api.create.return_value.device.return_value
    mock_device.get_picture_blobs.return_value = [b"blob1"]

    # Make decode_picture return a result with no timestamp
    photo_result = MagicMock()
    photo_bytes = b"imagedata"
    photo_result.data = photo_bytes
    photo_result.mime_type = "image/jpeg"
    photo_result.timestamp = None
    mock_device.decode_picture.return_value = photo_result

    # Make Image.open to raise when used which should trigger EXIF warning
    with patch("PIL.Image.open", side_effect=Exception("exif fail")):
        await btn.async_press()

    assert any(
        "Could not extract EXIF timestamp" in rec.getMessage()
        or "Could not extract EXIF timestamp" in rec.message
        for rec in caplog.records
    )


async def test_download_photos_write_raises_logs_error(
    hass: HomeAssistant, mock_fmd_api: AsyncMock, caplog
) -> None:
    """If writing a photo file fails, log an error and continue."""
    caplog.set_level(logging.ERROR)
    await setup_integration(hass, mock_fmd_api)

    btn = FmdDownloadPhotosButton(
        hass, hass.config_entries.async_entries(domain=DOMAIN)[0]
    )

    mock_device = mock_fmd_api.create.return_value.device.return_value
    mock_device.get_picture_blobs.return_value = [b"blob1"]

    # Make decode_picture return a result
    photo_result = MagicMock()
    photo_bytes = b"imagedata2"
    photo_result.data = photo_bytes
    photo_result.mime_type = "image/jpeg"
    photo_result.timestamp = None
    mock_device.decode_picture.return_value = photo_result

    # Patch Path.write_bytes to raise
    with patch("pathlib.Path.write_bytes", side_effect=Exception("write fail")):
        await btn.async_press()

    assert any("Failed to decrypt/save photo" in rec.message for rec in caplog.records)
