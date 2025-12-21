"""Tests for the iCloud camera."""

from collections.abc import Iterable
import datetime
from types import MappingProxyType
from unittest.mock import MagicMock, patch

from pyicloud.exceptions import (
    PyiCloudAPIResponseException,
    PyiCloudServiceNotActivatedException,
)
from pyicloud.services.photos import PhotoStreamAsset
import pytest

from homeassistant.components.icloud.camera import (
    AppleiCloudAlbumCamera,
    AppleiCloudSharedStreamCamera,
    async_setup_entry,
)
from homeassistant.components.icloud.const import (
    CONF_ALBUM_ID,
    CONF_ALBUM_NAME,
    CONF_ALBUM_TYPE,
    CONF_PICTURE_INTERVAL,
    CONF_RANDOM_ORDER,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from tests.common import MockConfigEntry


@pytest.fixture
def album_subentry() -> ConfigSubentry:
    """Create a config subentry for an album camera."""
    return ConfigSubentry(
        data=MappingProxyType(
            {
                CONF_ALBUM_ID: "album123",
                CONF_ALBUM_NAME: "My Album",
                CONF_ALBUM_TYPE: "album",
                CONF_PICTURE_INTERVAL: 300.0,
                CONF_RANDOM_ORDER: False,
            }
        ),
        subentry_type="camera",
        title="Test Album",
        unique_id="album123",
    )


@pytest.fixture
def shared_stream_subentry() -> ConfigSubentry:
    """Create a config subentry for a shared stream camera."""
    return ConfigSubentry(
        data=MappingProxyType(
            {
                CONF_ALBUM_ID: "stream456",
                CONF_ALBUM_NAME: "My Stream",
                CONF_ALBUM_TYPE: "shared_stream",
                CONF_PICTURE_INTERVAL: 600.0,
                CONF_RANDOM_ORDER: True,
            }
        ),
        subentry_type="camera",
        title="Test Stream",
        unique_id="stream456",
    )


async def test_icloud_camera_basic_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
    shared_stream_subentry: ConfigSubentry,
) -> None:
    """Test basic setup of iCloud camera entities."""

    mock_config_entry.runtime_data = MagicMock()
    mock_config_entry.runtime_data.api = mock_icloud_service
    hass.config_entries.async_add_subentry(mock_config_entry, album_subentry)
    hass.config_entries.async_add_subentry(mock_config_entry, shared_stream_subentry)

    entities = []

    class MockAddEntities(AddConfigEntryEntitiesCallback):
        def __call__(
            self,
            new_entities: Iterable[Entity],
            update_before_add: bool = False,
            *,
            config_subentry_id: str | None = None,
        ) -> None:
            entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, MockAddEntities())

    assert len(entities) == 2

    # Check album camera
    album_camera: AppleiCloudAlbumCamera = next(
        e
        for e in entities
        if isinstance(e, AppleiCloudAlbumCamera) and e._type == "album"
    )
    assert album_camera._id == "album123"
    assert album_camera._random is False
    assert album_camera.unique_id == "album_album123"

    # Check shared stream camera
    stream_camera: AppleiCloudSharedStreamCamera = next(
        e for e in entities if isinstance(e, AppleiCloudSharedStreamCamera)
    )
    assert stream_camera._id == "stream456"
    assert stream_camera._random is True
    assert stream_camera.unique_id == "shared_stream_stream456"


async def test_icloud_camera_album_loading_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
) -> None:
    """Test successful album loading."""
    mock_album = MagicMock()
    mock_album.title = "My Test Album"
    mock_album.get.return_value = mock_album

    mock_icloud_service.photos.albums.get.return_value = mock_album

    camera = AppleiCloudAlbumCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )
    camera.hass = hass
    camera.entity_id = "camera.test_album"

    await camera._load_album()

    assert camera._album == mock_album
    assert camera._attr_available is True
    assert camera._attr_name == "My Test Album Album"


async def test_icloud_camera_album_loading_service_not_activated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
) -> None:
    """Test album loading when Photos service is not activated."""
    mock_icloud_service.photos.albums = MagicMock()
    mock_icloud_service.photos.albums.get.side_effect = (
        PyiCloudServiceNotActivatedException("Service not activated")
    )

    camera = AppleiCloudAlbumCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )
    camera.hass = hass
    camera.entity_id = "camera.test_album"

    with pytest.raises(PyiCloudServiceNotActivatedException):
        await camera._load_album()

    assert camera._album is None
    assert camera._attr_available is False


async def test_icloud_camera_album_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
) -> None:
    """Test when album is not found."""
    mock_icloud_service.photos.albums.get.return_value = None

    camera = AppleiCloudAlbumCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )
    camera.hass = hass
    camera.entity_id = "camera.test_album"

    await camera._load_album()

    assert camera._album is None
    assert camera._attr_available is False


async def test_icloud_camera_availability_conditions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
) -> None:
    """Test camera availability under different conditions."""
    camera = AppleiCloudAlbumCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )

    # Initially not available - missing components
    assert camera.available is False

    # Set available flag but still missing components
    camera._attr_available = True
    assert camera.available is False

    # Add album
    camera._album = MagicMock()
    assert camera.available is False

    # Add photo
    camera._photo = MagicMock()
    assert camera.available is False

    # Add image - now should be available
    camera._image = b"fake_image_data"
    assert camera.available is True

    # Remove API - should be unavailable
    camera._api = None
    assert camera.available is False


async def test_icloud_camera_async_camera_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
) -> None:
    """Test retrieving camera image."""

    camera = AppleiCloudAlbumCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )
    camera._album = MagicMock()
    camera._image = b"test_image_data"

    # Test with enabled camera
    camera._attr_is_on = True
    image_data: bytes = await camera.async_camera_image()
    assert image_data == b"test_image_data"

    # Test with disabled camera
    camera._attr_is_on = False
    image_data = await camera.async_camera_image()
    assert image_data == b""

    # Test with no album
    camera._attr_is_on = True
    camera._album = None
    image_data = await camera.async_camera_image()
    assert image_data == b""

    # Test with no image data
    camera._album = MagicMock()
    camera._image = None
    image_data = await camera.async_camera_image()
    assert image_data == b""


async def test_icloud_camera_next_image_sequential(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
) -> None:
    """Test sequential image loading."""
    mock_photo1 = MagicMock()
    mock_photo1.id = "photo1"
    mock_photo1.download.return_value = b"image1_data"
    mock_photo1.created = datetime.datetime(2023, 1, 1)
    mock_photo1.is_live_photo = False
    mock_photo1.dimensions = (1920, 1080)
    mock_photo1.filename = "photo1.jpg"
    mock_photo1.item_type = "image"

    mock_photo2 = MagicMock()
    mock_photo2.id = "photo2"
    mock_photo2.download.return_value = b"image2_data"
    mock_photo2.created = datetime.datetime(2023, 1, 2)
    mock_photo2.is_live_photo = True
    mock_photo2.dimensions = (1920, 1080)
    mock_photo2.filename = "photo2.jpg"
    mock_photo2.item_type = "image"

    mock_album = MagicMock()
    mock_album.__len__ = MagicMock(return_value=2)
    mock_album.photo = MagicMock(side_effect=[mock_photo1, mock_photo2, mock_photo1])

    camera = AppleiCloudAlbumCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )
    camera.hass = hass
    camera.entity_id = "camera.test_album"
    camera._album = mock_album
    camera._random = False
    hass.add_job = MagicMock()  # pyright: ignore[reportAttributeAccessIssue]

    # First image
    camera._next_image()
    assert camera.current_photo_index == 1
    assert camera._photo == mock_photo1
    assert camera._image == b"image1_data"
    assert hass.add_job.call_count == 2  # pyright: ignore[reportAttributeAccessIssue]

    hass.add_job = MagicMock()  # pyright: ignore[reportAttributeAccessIssue]

    # Second image
    camera._next_image()
    assert camera.current_photo_index == 0  # Wraps around
    assert camera._photo == mock_photo2
    assert camera._image == b"image2_data"
    assert hass.add_job.call_count == 3  # pyright: ignore[reportAttributeAccessIssue]

    hass.add_job = MagicMock()  # pyright: ignore[reportAttributeAccessIssue]

    # Third image (wraps to beginning)
    camera._next_image()
    assert camera.current_photo_index == 1
    assert camera._photo == mock_photo1
    assert camera._image == b"image1_data"
    assert hass.add_job.call_count == 2  # pyright: ignore[reportAttributeAccessIssue]


@patch("homeassistant.components.icloud.camera.random.randint")
async def test_icloud_camera_next_image_random(
    mock_randint: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
) -> None:
    """Test random image loading."""
    mock_randint.return_value = 2

    mock_photo = MagicMock()
    mock_photo.id = "photo3"
    mock_photo.download.return_value = b"image3_data"
    mock_photo.created = datetime.datetime(2023, 1, 3)
    mock_photo.is_live_photo = False
    mock_photo.dimensions = (1920, 1080)
    mock_photo.filename = "photo3.jpg"
    mock_photo.item_type = "image"

    mock_album = MagicMock()
    mock_album.__len__ = MagicMock(return_value=5)
    mock_album.photo = MagicMock(return_value=mock_photo)

    camera = AppleiCloudAlbumCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )
    camera.hass = hass
    camera.entity_id = "camera.test_album"
    camera._album = mock_album
    camera._random = True
    hass.add_job = MagicMock()  # pyright: ignore[reportAttributeAccessIssue]

    camera._next_image()

    mock_randint.assert_called_once_with(0, 4)
    assert camera.current_photo_index == 2
    assert camera._photo == mock_photo
    assert camera._image == b"image3_data"
    assert hass.add_job.called  # pyright: ignore[reportAttributeAccessIssue]


async def test_icloud_camera_next_image_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling API errors during image loading."""
    mock_album = MagicMock()
    mock_album.__len__ = MagicMock(return_value=2)
    mock_album.photo = MagicMock(side_effect=PyiCloudAPIResponseException("API Error"))

    camera = AppleiCloudAlbumCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )
    camera.hass = hass
    camera.entity_id = "camera.test_album"
    camera._album = mock_album
    hass.add_job = MagicMock()  # pyright: ignore[reportAttributeAccessIssue]

    camera._next_image()

    assert "Error loading photo at index" in caplog.text
    assert "API Error" in caplog.text


async def test_icloud_camera_next_image_empty_album(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
) -> None:
    """Test handling empty album."""
    mock_album = MagicMock()
    mock_album.__len__ = MagicMock(return_value=0)

    camera = AppleiCloudAlbumCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )
    camera.hass = hass
    camera._album = mock_album
    camera._current_photo_index = 0

    camera._next_image()

    # Should not change index for empty album
    assert camera.current_photo_index == 0
    mock_album.photo.assert_not_called()


async def test_icloud_camera_extra_state_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
) -> None:
    """Test extra state attributes."""
    mock_photo = MagicMock()
    mock_photo.id = "photo123"
    mock_photo.created = datetime.datetime(2023, 5, 15, 10, 30, 0)
    mock_photo.is_live_photo = True
    mock_photo.dimensions = (4032, 3024)
    mock_photo.filename = "IMG_1234.HEIC"
    mock_photo.item_type = "image/heic"

    mock_album = MagicMock()
    mock_album.__len__ = MagicMock(return_value=42)

    camera = AppleiCloudAlbumCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )
    camera._photo = mock_photo
    camera._album = mock_album

    attrs = camera.extra_state_attributes

    expected_attrs = {
        "photo_id": "photo123",
        "created": datetime.datetime(2023, 5, 15, 10, 30, 0),
        "is_live_photo": True,
        "dimensions": "4032x3024",
        "filename": "IMG_1234.HEIC",
        "total_photos": 42,
        "picture_type": "image/heic",
    }

    assert attrs == expected_attrs


async def test_icloud_camera_extra_state_attributes_no_photo(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
) -> None:
    """Test extra state attributes when no photo is loaded."""
    camera = AppleiCloudAlbumCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )
    camera._photo = None

    attrs = camera.extra_state_attributes
    assert attrs == {}


async def test_icloud_shared_stream_camera_extra_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
) -> None:
    """Test shared stream camera extra attributes."""
    mock_photo = MagicMock(spec=PhotoStreamAsset)
    mock_photo.id = "stream_photo123"
    mock_photo.created = datetime.datetime(2023, 5, 15, 10, 30, 0)
    mock_photo.is_live_photo = False
    mock_photo.dimensions = (1920, 1080)
    mock_photo.filename = "stream_photo.jpg"
    mock_photo.item_type = "image/jpeg"
    mock_photo.like_count = 5
    mock_photo.liked = True

    mock_album = MagicMock()
    mock_album.__len__ = MagicMock(return_value=10)

    camera = AppleiCloudSharedStreamCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )
    camera._photo = mock_photo
    camera._album = mock_album

    attrs = camera.extra_state_attributes

    assert "like_count" in attrs
    assert attrs["like_count"] == 5
    assert "liked" in attrs
    assert attrs["liked"] is True


async def test_icloud_camera_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
) -> None:
    """Test turning camera on and off."""

    camera = AppleiCloudAlbumCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )
    camera.hass = hass
    camera.entity_id = "camera.test_album"

    # Test turn on
    await camera.async_turn_on()
    assert camera._attr_is_on is True

    # Test turn off
    await camera.async_turn_off()
    assert camera._attr_is_on is False


@patch("homeassistant.components.icloud.camera.async_track_time_interval")
async def test_icloud_camera_timer_setup(
    mock_track_time_interval: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
) -> None:
    """Test timer setup for automatic image updates."""

    camera = AppleiCloudAlbumCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )
    camera.hass = hass
    camera.entity_id = "camera.test_album"
    camera.async_on_remove = MagicMock()

    await camera.async_added_to_hass()

    mock_track_time_interval.assert_called_once()
    call_args = mock_track_time_interval.call_args
    assert call_args[1]["interval"] == datetime.timedelta(seconds=300.0)
    assert call_args[1]["action"] == camera._handle_timer_update

    camera.async_on_remove.assert_called_once()


async def test_icloud_camera_timer_disabled_when_interval_zero(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
) -> None:
    """Test timer is not set up when interval is 0."""
    with patch(
        "homeassistant.components.icloud.camera.async_track_time_interval"
    ) as mock_track:
        subentry = ConfigSubentry(
            data=MappingProxyType(
                {
                    CONF_ALBUM_ID: "album123",
                    CONF_ALBUM_NAME: "My Album",
                    CONF_ALBUM_TYPE: "album",
                    CONF_PICTURE_INTERVAL: 0.0,
                    CONF_RANDOM_ORDER: False,
                }
            ),
            subentry_type="camera",
            title="Test Album",
            unique_id="album123",
        )

        camera = AppleiCloudAlbumCamera(
            mock_icloud_service, mock_config_entry, subentry
        )
        camera.hass = hass
        camera.entity_id = "camera.test_album"

        await camera.async_added_to_hass()

        mock_track.assert_not_called()


async def test_icloud_camera_config_entry_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_icloud_service: MagicMock,
    album_subentry: ConfigSubentry,
) -> None:
    """Test updating config entry when photo index changes."""
    mock_album = MagicMock()
    mock_album.__len__ = MagicMock(return_value=10)

    camera = AppleiCloudAlbumCamera(
        mock_icloud_service, mock_config_entry, album_subentry
    )
    camera.hass = hass
    camera.entity_id = "camera.test_album"
    camera._album = mock_album

    hass.config_entries.async_update_subentry = MagicMock()
    hass.add_job = MagicMock()  # pyright: ignore[reportAttributeAccessIssue]

    # Update photo index
    camera.current_photo_index = 7

    hass.add_job.assert_called_once_with(camera._update_entry)  # pyright: ignore[reportAttributeAccessIssue]

    camera._update_entry()

    hass.config_entries.async_update_subentry.assert_called_once_with(
        entry=mock_config_entry,
        subentry=album_subentry,
        data={
            CONF_ALBUM_ID: "album123",
            CONF_ALBUM_NAME: "My Album",
            CONF_ALBUM_TYPE: "album",
            CONF_PICTURE_INTERVAL: 300.0,
            CONF_RANDOM_ORDER: False,
            "current_photo_index": 7,
        },
    )
