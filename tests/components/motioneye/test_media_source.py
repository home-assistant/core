"""Test Local Media Source."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import client_exceptions
from motioneye_client.client import MotionEyeClientError
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
from homeassistant.components.motioneye.media_source import async_get_media_source
from homeassistant.config_entries import ConfigEntryState
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

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

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


class MockStreamContent:
    """Mock an aiohttp streaming response body."""

    def __init__(self, data: bytes) -> None:
        """Initialize mock streaming content."""
        self.data = data

    async def iter_chunked(self, size: int) -> AsyncIterator[bytes]:
        """Yield response data in chunks."""
        for offset in range(0, len(self.data), size):
            yield self.data[offset : offset + size]


def mock_media_stream(
    client,
    data: bytes,
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Mock motionEye saved-media streaming."""
    stream_mock = MagicMock()

    @asynccontextmanager
    async def stream(*args, **kwargs):
        yield SimpleNamespace(
            status=status,
            headers=headers or {},
            content=MockStreamContent(data),
        )

    stream_mock.side_effect = stream
    client.async_get_media_stream = stream_mock
    return stream_mock


@pytest.fixture(autouse=True)
def mock_sign_path() -> None:
    """Return a deterministic signed media proxy URL."""
    with patch(
        "homeassistant.components.motioneye.media_source.async_sign_path",
        return_value="http://signed",
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_media_source(hass: HomeAssistant) -> None:
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
        "can_search": False,
        "search_media_classes": None,
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
                "can_search": False,
                "search_media_classes": None,
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
        "can_search": False,
        "search_media_classes": None,
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
                "can_search": False,
                "search_media_classes": None,
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
        "can_search": False,
        "search_media_classes": None,
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
                "can_search": False,
                "search_media_classes": None,
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
                "can_search": False,
                "search_media_classes": None,
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
        "can_search": False,
        "search_media_classes": None,
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
                "can_search": False,
                "search_media_classes": None,
                "thumbnail": None,
                "children_media_class": "directory",
            }
        ],
        "not_shown": 0,
    }

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
        "can_search": False,
        "search_media_classes": None,
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
                "can_search": False,
                "search_media_classes": None,
                "thumbnail": "http://signed",
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
                "can_search": False,
                "search_media_classes": None,
                "thumbnail": "http://signed",
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
                "can_search": False,
                "search_media_classes": None,
                "thumbnail": "http://signed",
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
        "can_search": False,
        "search_media_classes": None,
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
                "can_search": False,
                "search_media_classes": None,
                "thumbnail": "http://signed",
                "children_media_class": None,
            }
        ],
        "not_shown": 0,
    }


async def test_media_proxy_image(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test fetching saved image media through the Home Assistant proxy."""
    client = create_mock_motioneye_client()
    stream_mock = mock_media_stream(
        client,
        b"image",
        headers={"Content-Type": "image/jpeg", "Content-Length": "5"},
    )
    config = await setup_mock_motioneye_config_entry(hass, client=client)
    await async_get_media_source(hass)

    client_session = await hass_client()
    response = await client_session.get(
        f"/api/motioneye/media/{config.entry_id}/1/images/0/L2Zvby5qcGc="
    )

    assert response.status == 200
    assert response.content_type == "image/jpeg"
    assert response.headers["Content-Length"] == "5"
    assert await response.read() == b"image"
    stream_mock.assert_called_once_with(
        1,
        "/foo.jpg",
        image=True,
        preview=False,
        range_header=None,
    )


async def test_media_proxy_movie_preview(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test fetching a movie preview through the Home Assistant proxy."""
    client = create_mock_motioneye_client()
    stream_mock = mock_media_stream(client, b"preview")
    config = await setup_mock_motioneye_config_entry(hass, client=client)
    await async_get_media_source(hass)

    client_session = await hass_client()
    response = await client_session.get(
        f"/api/motioneye/media/{config.entry_id}/1/movies/1/L2Zvby5tcDQ="
    )

    assert response.status == 200
    assert response.content_type == "image/jpeg"
    assert await response.read() == b"preview"
    stream_mock.assert_called_once_with(
        1,
        "/foo.mp4",
        image=False,
        preview=True,
        range_header=None,
    )


async def test_media_proxy_movie_range(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test forwarding a Range request and partial-content response."""
    client = create_mock_motioneye_client()
    stream_mock = mock_media_stream(
        client,
        b"0123",
        status=206,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": "4",
            "Content-Range": "bytes 0-3/10",
            "Content-Type": "video/mp4",
        },
    )
    config = await setup_mock_motioneye_config_entry(hass, client=client)
    await async_get_media_source(hass)

    client_session = await hass_client()
    response = await client_session.get(
        f"/api/motioneye/media/{config.entry_id}/1/movies/0/L2Zvby5tcDQ=",
        headers={"Range": "bytes=0-3"},
    )

    assert response.status == 206
    assert response.content_type == "video/mp4"
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Content-Length"] == "4"
    assert response.headers["Content-Range"] == "bytes 0-3/10"
    assert await response.read() == b"0123"
    stream_mock.assert_called_once_with(
        1,
        "/foo.mp4",
        image=False,
        preview=False,
        range_header="bytes=0-3",
    )


async def test_media_proxy_movie_range_not_satisfiable(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test forwarding an unsatisfiable Range response."""
    client = create_mock_motioneye_client()
    stream_mock = mock_media_stream(
        client,
        b"",
        status=416,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": "bytes */10",
        },
    )
    config = await setup_mock_motioneye_config_entry(hass, client=client)
    await async_get_media_source(hass)

    client_session = await hass_client()
    response = await client_session.get(
        f"/api/motioneye/media/{config.entry_id}/1/movies/0/L2Zvby5tcDQ=",
        headers={"Range": "bytes=100-200"},
    )

    assert response.status == 416
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Content-Range"] == "bytes */10"
    assert await response.read() == b""
    stream_mock.assert_called_once_with(
        1,
        "/foo.mp4",
        image=False,
        preview=False,
        range_header="bytes=100-200",
    )


async def test_media_proxy_client_error(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test handling a motionEye client error while opening saved media."""
    client = create_mock_motioneye_client()

    class FailingStream:
        async def __aenter__(self) -> None:
            raise MotionEyeClientError

        async def __aexit__(self, *args: object) -> None:
            """No cleanup: stream never opened."""

    stream_mock = MagicMock(return_value=FailingStream())
    client.async_get_media_stream = stream_mock

    config = await setup_mock_motioneye_config_entry(hass, client=client)
    await async_get_media_source(hass)

    client_session = await hass_client()
    response = await client_session.get(
        f"/api/motioneye/media/{config.entry_id}/1/movies/0/L2Zvby5tcDQ="
    )

    assert response.status == 502
    stream_mock.assert_called_once_with(
        1,
        "/foo.mp4",
        image=False,
        preview=False,
        range_header=None,
    )


async def test_media_proxy_client_error_after_response_started(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test a motionEye client error after the media response has started."""
    client = create_mock_motioneye_client()

    class FailingStreamContent:
        async def iter_chunked(self, size: int) -> AsyncIterator[bytes]:
            yield b"movie"
            raise MotionEyeClientError

    @asynccontextmanager
    async def media_stream(*args, **kwargs):
        yield SimpleNamespace(
            status=200,
            headers={"Content-Type": "video/mp4"},
            content=FailingStreamContent(),
        )

    stream_mock = MagicMock(side_effect=media_stream)
    client.async_get_media_stream = stream_mock

    config = await setup_mock_motioneye_config_entry(hass, client=client)
    await async_get_media_source(hass)

    client_session = await hass_client()
    response = await client_session.get(
        f"/api/motioneye/media/{config.entry_id}/1/movies/0/L2Zvby5tcDQ="
    )

    assert response.status == 200
    assert await response.content.readexactly(5) == b"movie"
    with pytest.raises(client_exceptions.ClientPayloadError):
        await response.content.read()
    stream_mock.assert_called_once_with(
        1,
        "/foo.mp4",
        image=False,
        preview=False,
        range_header=None,
    )


async def test_media_proxy_rejects_invalid_kind(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test rejecting an invalid media kind."""
    client = create_mock_motioneye_client()
    stream_mock = mock_media_stream(client, b"")
    config = await setup_mock_motioneye_config_entry(hass, client=client)
    await async_get_media_source(hass)

    client_session = await hass_client()
    response = await client_session.get(
        f"/api/motioneye/media/{config.entry_id}/1/invalid/0/L2Zvby5qcGc="
    )

    assert response.status == 400
    stream_mock.assert_not_called()


async def test_media_proxy_rejects_non_ascii_path(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test rejecting a malformed non-ASCII encoded media path."""
    client = create_mock_motioneye_client()
    stream_mock = mock_media_stream(client, b"")
    config = await setup_mock_motioneye_config_entry(hass, client=client)
    await async_get_media_source(hass)

    client_session = await hass_client()
    response = await client_session.get(
        f"/api/motioneye/media/{config.entry_id}/1/images/0/ż"
    )

    assert response.status == 400
    stream_mock.assert_not_called()


async def test_media_proxy_rejects_invalid_base64_path(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test rejecting malformed ASCII Base64 media path."""
    client = create_mock_motioneye_client()
    stream_mock = mock_media_stream(client, b"")
    config = await setup_mock_motioneye_config_entry(hass, client=client)
    await async_get_media_source(hass)

    client_session = await hass_client()
    response = await client_session.get(
        f"/api/motioneye/media/{config.entry_id}/1/images/0/!!!!"
    )

    assert response.status == 400
    stream_mock.assert_not_called()


async def test_media_proxy_rejects_relative_path(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test rejecting a relative media path."""
    client = create_mock_motioneye_client()
    stream_mock = mock_media_stream(client, b"")
    config = await setup_mock_motioneye_config_entry(hass, client=client)
    await async_get_media_source(hass)

    client_session = await hass_client()
    response = await client_session.get(
        f"/api/motioneye/media/{config.entry_id}/1/images/0/Zm9vLmpwZw=="
    )

    assert response.status == 400
    stream_mock.assert_not_called()


async def test_media_proxy_rejects_parent_directory_traversal(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test rejecting a media path containing parent-directory traversal."""
    client = create_mock_motioneye_client()
    stream_mock = mock_media_stream(client, b"")
    config = await setup_mock_motioneye_config_entry(hass, client=client)
    await async_get_media_source(hass)

    client_session = await hass_client()
    response = await client_session.get(
        f"/api/motioneye/media/{config.entry_id}/1/images/0/"
        "L3JlY29yZGluZ3MvLi4vc2VjcmV0"
    )

    assert response.status == 400
    stream_mock.assert_not_called()


async def test_media_proxy_rejects_config_entry_from_other_domain(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test rejecting a config entry from another domain."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    config = MockConfigEntry(
        domain="test",
        state=ConfigEntryState.LOADED,
    )
    config.add_to_hass(hass)

    client_session = await hass_client()
    response = await client_session.get(
        f"/api/motioneye/media/{config.entry_id}/1/images/0/L2Zvby5qcGc="
    )

    assert response.status == 404


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
    media = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{TEST_CONFIG_ENTRY_ID}#{device.id}#movies#/foo.mp4",
        None,
    )
    assert media == PlayMedia(
        url=(
            f"/api/motioneye/media/{TEST_CONFIG_ENTRY_ID}/{TEST_CAMERA_ID}/"
            "movies/0/L2Zvby5tcDQ="
        ),
        mime_type="video/mp4",
    )

    # Test successful resolve for an image.
    media = await async_resolve_media(
        hass,
        f"{URI_SCHEME}{DOMAIN}/{TEST_CONFIG_ENTRY_ID}#{device.id}#images#/foo.jpg",
        None,
    )
    assert media == PlayMedia(
        url=(
            f"/api/motioneye/media/{TEST_CONFIG_ENTRY_ID}/{TEST_CAMERA_ID}/"
            "images/0/L2Zvby5qcGc="
        ),
        mime_type="image/jpeg",
    )


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

    # Media path does not start with '/'
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
        "can_search": False,
        "search_media_classes": None,
        "children_media_class": "video",
        "thumbnail": None,
        "children": [],
        "not_shown": 0,
    }
