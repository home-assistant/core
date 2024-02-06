"""Test Local Media Source."""
import logging
from unittest.mock import AsyncMock, Mock, call

from motioneye_client.client import MotionEyeClientPathError
import pytest

from homeassistant.components.media_source import (
    URI_SCHEME,
    MediaSourceError,
    PlayMedia,
    Unresolvable,
    async_browse_media,
    async_resolve_media,
)
from homeassistant.components.motioneye.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from . import (
    TEST_CAMERA_DEVICE_IDENTIFIER,
    TEST_CAMERA_ID,
    TEST_CONFIG_ENTRY_ID,
    create_mock_motioneye_client,
    setup_mock_motioneye_config_entry,
)

TEST_MOVIES = {
    "mediaList": [
        {
            "mimeType": "video/mp4",
            "sizeStr": "4.7 MB",
            "momentStrShort": "25 Apr, 00:26",
            "timestamp": 1619335614.0353653,
            "momentStr": "25 April 2021, 00:26",
            "path": "/2021-04-25/00-26-22.mp4",
        },
        {
            "mimeType": "video/mp4",
            "sizeStr": "9.2 MB",
            "momentStrShort": "25 Apr, 00:37",
            "timestamp": 1619336268.0683491,
            "momentStr": "25 April 2021, 00:37",
            "path": "/2021-04-25/00-36-49.mp4",
        },
        {
            "mimeType": "video/mp4",
            "sizeStr": "28.3 MB",
            "momentStrShort": "25 Apr, 00:03",
            "timestamp": 1619334211.0403328,
            "momentStr": "25 April 2021, 00:03",
            "path": "/2021-04-25/00-02-27.mp4",
        },
    ]
}

TEST_IMAGES = {
    "mediaList": [
        {
            "mimeType": "image/jpeg",
            "sizeStr": "216.5 kB",
            "momentStrShort": "12 Apr, 20:13",
            "timestamp": 1618283619.6541321,
            "momentStr": "12 April 2021, 20:13",
            "path": "/2021-04-12/20-13-39.jpg",
        }
    ],
}


_LOGGER = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
async def setup_media_source(hass) -> None:
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})


async def test_async_browse_media_success(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test successful browse media."""

    client = create_mock_motioneye_client()
    config = await setup_mock_motioneye_config_entry(hass, client=client)

    device = device_registry.async_get_or_create(
        config_entry_id=config.entry_id,
        identifiers={TEST_CAMERA_DEVICE_IDENTIFIER},
    )

    media = await async_browse_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}",
    )

    assert media.as_dict() == {
        "title": "motionEye Media",
        "media_class": "directory",
        "media_content_type": "",
        "media_content_id": "media-source://motioneye",
        "can_play": False,
        "can_expand": True,
        "children_media_class": "directory",
        "thumbnail": None,
        "children": [
            {
                "title": "http://test:8766",
                "media_class": "directory",
                "media_content_type": "",
                "media_content_id": (
                    "media-source://motioneye/74565ad414754616000674c87bdc876c"
                ),
                "can_play": False,
                "can_expand": True,
                "thumbnail": None,
                "children_media_class": "directory",
            }
        ],
        "not_shown": 0,
    }

    media = await async_browse_media(hass, f"{URI_SCHEME}{DOMAIN}/{config.entry_id}")

    assert media.as_dict() == {
        "title": "http://test:8766",
        "media_class": "directory",
        "media_content_type": "",
        "media_content_id": "media-source://motioneye/74565ad414754616000674c87bdc876c",
        "can_play": False,
        "can_expand": True,
        "children_media_class": "directory",
        "thumbnail": None,
        "children": [
            {
                "title": "Test Camera",
                "media_class": "directory",
                "media_content_type": "",
                "media_content_id": (
                    "media-source://motioneye"
                    f"/74565ad414754616000674c87bdc876c#{device.id}"
                ),
                "can_play": False,
                "can_expand": True,
                "thumbnail": None,
                "children_media_class": "directory",
            }
        ],
        "not_shown": 0,
    }

    media = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/{config.entry_id}#{device.id}"
    )
    assert media.as_dict() == {
        "title": "http://test:8766 Test Camera",
        "media_class": "directory",
        "media_content_type": "",
        "media_content_id": (
            f"media-source://motioneye/74565ad414754616000674c87bdc876c#{device.id}"
        ),
        "can_play": False,
        "can_expand": True,
        "children_media_class": "directory",
        "thumbnail": None,
        "children": [
            {
                "title": "Movies",
                "media_class": "directory",
                "media_content_type": "video",
                "media_content_id": (
                    "media-source://motioneye"
                    f"/74565ad414754616000674c87bdc876c#{device.id}#movies"
                ),
                "can_play": False,
                "can_expand": True,
                "thumbnail": None,
                "children_media_class": "video",
            },
            {
                "title": "Images",
                "media_class": "directory",
                "media_content_type": "image",
                "media_content_id": (
                    "media-source://motioneye"
                    f"/74565ad414754616000674c87bdc876c#{device.id}#images"
                ),
                "can_play": False,
                "can_expand": True,
                "thumbnail": None,
                "children_media_class": "image",
            },
        ],
        "not_shown": 0,
    }

    client.async_get_movies = AsyncMock(return_value=TEST_MOVIES)
    media = await async_browse_media(
        hass, f"{URI_SCHEME}{DOMAIN}/{config.entry_id}#{device.id}#movies"
    )

    assert media.as_dict() == {
        "title": "http://test:8766 Test Camera Movies",
        "media_class": "directory",
        "media_content_type": "video",
        "media_content_id": (
            "media-source://motioneye"
            f"/74565ad414754616000674c87bdc876c#{device.id}#movies"
        ),
        "can_play": False,
        "can_expand": True,
        "children_media_class": "video",
        "thumbnail": None,
        "children": [
            {
                "title": "2021-04-25",
                "media_class": "directory",
                "media_content_type": "video",
                "media_content_id": (
                    "media-source://motioneye"
                    f"/74565ad414754616000674c87bdc876c#{device.id}#movies#/2021-04-25"
                ),
                "can_play": False,
                "can_expand": True,
                "thumbnail": None,
                "children_media_class": "directory",
            }
        ],
        "not_shown": 0,
    }

    client.get_movie_url = Mock(return_value="http://movie")
    media = await async_browse_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{config.entry_id}#{device.id}#movies#/2021-04-25",
    )
    assert media.as_dict() == {
        "title": "http://test:8766 Test Camera Movies 2021-04-25",
        "media_class": "directory",
        "media_content_type": "video",
        "media_content_id": (
            "media-source://motioneye"
            f"/74565ad414754616000674c87bdc876c#{device.id}#movies"
        ),
        "can_play": False,
        "can_expand": True,
        "children_media_class": "video",
        "thumbnail": None,
        "children": [
            {
                "title": "00-02-27.mp4",
                "media_class": "video",
                "media_content_type": "video/mp4",
                "media_content_id": (
                    "media-source://motioneye"
                    f"/74565ad414754616000674c87bdc876c#{device.id}#movies#"
                    "/2021-04-25/00-02-27.mp4"
                ),
                "can_play": True,
                "can_expand": False,
                "thumbnail": "http://movie",
                "children_media_class": None,
            },
            {
                "title": "00-26-22.mp4",
                "media_class": "video",
                "media_content_type": "video/mp4",
                "media_content_id": (
                    "media-source://motioneye"
                    f"/74565ad414754616000674c87bdc876c#{device.id}#movies#"
                    "/2021-04-25/00-26-22.mp4"
                ),
                "can_play": True,
                "can_expand": False,
                "thumbnail": "http://movie",
                "children_media_class": None,
            },
            {
                "title": "00-36-49.mp4",
                "media_class": "video",
                "media_content_type": "video/mp4",
                "media_content_id": (
                    "media-source://motioneye"
                    f"/74565ad414754616000674c87bdc876c#{device.id}#movies#"
                    "/2021-04-25/00-36-49.mp4"
                ),
                "can_play": True,
                "can_expand": False,
                "thumbnail": "http://movie",
                "children_media_class": None,
            },
        ],
        "not_shown": 0,
    }


async def test_async_browse_media_images_success(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test successful browse media of images."""

    client = create_mock_motioneye_client()
    config = await setup_mock_motioneye_config_entry(hass, client=client)

    device = device_registry.async_get_or_create(
        config_entry_id=config.entry_id,
        identifiers={TEST_CAMERA_DEVICE_IDENTIFIER},
    )

    client.async_get_images = AsyncMock(return_value=TEST_IMAGES)
    client.get_image_url = Mock(return_value="http://image")

    media = await async_browse_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{config.entry_id}#{device.id}#images#/2021-04-12",
    )
    assert media.as_dict() == {
        "title": "http://test:8766 Test Camera Images 2021-04-12",
        "media_class": "directory",
        "media_content_type": "image",
        "media_content_id": (
            "media-source://motioneye"
            f"/74565ad414754616000674c87bdc876c#{device.id}#images"
        ),
        "can_play": False,
        "can_expand": True,
        "children_media_class": "image",
        "thumbnail": None,
        "children": [
            {
                "title": "20-13-39.jpg",
                "media_class": "image",
                "media_content_type": "image/jpeg",
                "media_content_id": (
                    "media-source://motioneye"
                    f"/74565ad414754616000674c87bdc876c#{device.id}#images#"
                    "/2021-04-12/20-13-39.jpg"
                ),
                "can_play": False,
                "can_expand": False,
                "thumbnail": "http://image",
                "children_media_class": None,
            }
        ],
        "not_shown": 0,
    }


async def test_async_resolve_media_success(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test successful resolve media."""

    client = create_mock_motioneye_client()

    config = await setup_mock_motioneye_config_entry(hass, client=client)

    device = device_registry.async_get_or_create(
        config_entry_id=config.entry_id,
        identifiers={TEST_CAMERA_DEVICE_IDENTIFIER},
    )

    # Test successful resolve for a movie.
    client.get_movie_url = Mock(return_value="http://movie-url")
    media = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{TEST_CONFIG_ENTRY_ID}#{device.id}#movies#/foo.mp4",
        None,
    )
    assert media == PlayMedia(url="http://movie-url", mime_type="video/mp4")
    assert client.get_movie_url.call_args == call(TEST_CAMERA_ID, "/foo.mp4")

    # Test successful resolve for an image.
    client.get_image_url = Mock(return_value="http://image-url")
    media = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{TEST_CONFIG_ENTRY_ID}#{device.id}#images#/foo.jpg",
        None,
    )
    assert media == PlayMedia(url="http://image-url", mime_type="image/jpeg")
    assert client.get_image_url.call_args == call(TEST_CAMERA_ID, "/foo.jpg")


async def test_async_resolve_media_failure(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test failed resolve media calls."""

    client = create_mock_motioneye_client()

    config = await setup_mock_motioneye_config_entry(hass, client=client)

    device = device_registry.async_get_or_create(
        config_entry_id=config.entry_id,
        identifiers={TEST_CAMERA_DEVICE_IDENTIFIER},
    )

    broken_device_1 = device_registry.async_get_or_create(
        config_entry_id=config.entry_id,
        identifiers={(DOMAIN, config.entry_id)},
    )
    broken_device_2 = device_registry.async_get_or_create(
        config_entry_id=config.entry_id,
        identifiers={(DOMAIN, f"{config.entry_id}_NOTINT")},
    )
    client.get_movie_url = Mock(return_value="http://url")

    # URI doesn't contain necessary components.
    with pytest.raises(Unresolvable):
        await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}/foo", None)

    # Config entry doesn't exist.
    with pytest.raises(MediaSourceError):
        await async_resolve_media(hass, f"{URI_SCHEME}{DOMAIN}/1#2#3#4", None)

    # Device doesn't exist.
    with pytest.raises(MediaSourceError):
        await async_resolve_media(
            hass, f"{URI_SCHEME}{DOMAIN}/{TEST_CONFIG_ENTRY_ID}#2#3#4", None
        )

    # Device identifiers are incorrect (no camera id)
    with pytest.raises(MediaSourceError):
        await async_resolve_media(
            hass,
            (
                f"{URI_SCHEME}{DOMAIN}"
                f"/{TEST_CONFIG_ENTRY_ID}#{broken_device_1.id}#images#4"
            ),
            None,
        )

    # Device identifiers are incorrect (non integer camera id)
    with pytest.raises(MediaSourceError):
        await async_resolve_media(
            hass,
            (
                f"{URI_SCHEME}{DOMAIN}"
                f"/{TEST_CONFIG_ENTRY_ID}#{broken_device_2.id}#images#4"
            ),
            None,
        )

    # Kind is incorrect.
    with pytest.raises(MediaSourceError):
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{TEST_CONFIG_ENTRY_ID}#{device.id}#games#moo",
            None,
        )

    # Playback URL raises exception.
    client.get_movie_url = Mock(side_effect=MotionEyeClientPathError)
    with pytest.raises(Unresolvable):
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{TEST_CONFIG_ENTRY_ID}#{device.id}#movies#/foo.mp4",
            None,
        )

    # Media path does not start with '/'
    client.get_movie_url = Mock(side_effect=MotionEyeClientPathError)
    with pytest.raises(MediaSourceError):
        await async_resolve_media(
            hass,
            f"{URI_SCHEME}{DOMAIN}/{TEST_CONFIG_ENTRY_ID}#{device.id}#movies#foo.mp4",
            None,
        )

    # Media missing path.
    broken_movies = {"mediaList": [{}, {"path": "something", "mimeType": "NOT_A_MIME"}]}
    client.async_get_movies = AsyncMock(return_value=broken_movies)
    media = await async_browse_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{config.entry_id}#{device.id}#movies#/2021-04-25",
    )
    assert media.as_dict() == {
        "title": "http://test:8766 Test Camera Movies 2021-04-25",
        "media_class": "directory",
        "media_content_type": "video",
        "media_content_id": (
            "media-source://motioneye"
            f"/74565ad414754616000674c87bdc876c#{device.id}#movies"
        ),
        "can_play": False,
        "can_expand": True,
        "children_media_class": "video",
        "thumbnail": None,
        "children": [],
        "not_shown": 0,
    }
