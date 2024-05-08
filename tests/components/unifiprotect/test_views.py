"""Test UniFi Protect views."""

from datetime import datetime, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

from aiohttp import ClientResponse
import pytest
from pyunifiprotect.data import Camera, Event, EventType
from pyunifiprotect.exceptions import ClientError

from homeassistant.components.unifiprotect.views import (
    async_generate_event_video_url,
    async_generate_thumbnail_url,
)
from homeassistant.core import HomeAssistant

from .utils import MockUFPFixture, init_entry

from tests.typing import ClientSessionGenerator


async def test_thumbnail_bad_nvr_id(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ufp: MockUFPFixture,
    camera: Camera,
) -> None:
    """Test invalid NVR ID in URL."""

    ufp.api.get_event_thumbnail = AsyncMock()

    await init_entry(hass, ufp, [camera])
    url = async_generate_thumbnail_url("test_id", "bad_id")

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(url))

    assert response.status == 404
    ufp.api.get_event_thumbnail.assert_not_called()


@pytest.mark.parametrize(("width", "height"), [("test", None), (None, "test")])
async def test_thumbnail_bad_params(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ufp: MockUFPFixture,
    camera: Camera,
    width: Any,
    height: Any,
) -> None:
    """Test invalid bad query parameters."""

    ufp.api.get_event_thumbnail = AsyncMock()

    await init_entry(hass, ufp, [camera])
    url = async_generate_thumbnail_url(
        "test_id", ufp.api.bootstrap.nvr.id, width=width, height=height
    )

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(url))

    assert response.status == 400
    ufp.api.get_event_thumbnail.assert_not_called()


async def test_thumbnail_bad_event(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ufp: MockUFPFixture,
    camera: Camera,
) -> None:
    """Test invalid with error raised."""

    ufp.api.get_event_thumbnail = AsyncMock(side_effect=ClientError())

    await init_entry(hass, ufp, [camera])
    url = async_generate_thumbnail_url("test_id", ufp.api.bootstrap.nvr.id)

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(url))

    assert response.status == 404
    ufp.api.get_event_thumbnail.assert_called_with("test_id", width=None, height=None)


async def test_thumbnail_no_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ufp: MockUFPFixture,
    camera: Camera,
) -> None:
    """Test invalid no thumbnail returned."""

    ufp.api.get_event_thumbnail = AsyncMock(return_value=None)

    await init_entry(hass, ufp, [camera])
    url = async_generate_thumbnail_url("test_id", ufp.api.bootstrap.nvr.id)

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(url))

    assert response.status == 404
    ufp.api.get_event_thumbnail.assert_called_with("test_id", width=None, height=None)


async def test_thumbnail(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ufp: MockUFPFixture,
    camera: Camera,
) -> None:
    """Test NVR ID in URL."""

    ufp.api.get_event_thumbnail = AsyncMock(return_value=b"testtest")

    await init_entry(hass, ufp, [camera])
    url = async_generate_thumbnail_url("test_id", ufp.api.bootstrap.nvr.id)

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(url))

    assert response.status == 200
    assert response.content_type == "image/jpeg"
    assert await response.content.read() == b"testtest"
    ufp.api.get_event_thumbnail.assert_called_with("test_id", width=None, height=None)


async def test_thumbnail_entry_id(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ufp: MockUFPFixture,
    camera: Camera,
) -> None:
    """Test config entry ID in URL."""

    ufp.api.get_event_thumbnail = AsyncMock(return_value=b"testtest")

    await init_entry(hass, ufp, [camera])
    url = async_generate_thumbnail_url("test_id", ufp.entry.entry_id)

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(url))

    assert response.status == 200
    assert response.content_type == "image/jpeg"
    assert await response.content.read() == b"testtest"
    ufp.api.get_event_thumbnail.assert_called_with("test_id", width=None, height=None)


async def test_video_bad_event(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test generating event with bad camera ID."""

    await init_entry(hass, ufp, [camera])

    event = Event(
        api=ufp.api,
        camera_id="test_id",
        start=fixed_now - timedelta(seconds=30),
        end=fixed_now,
        id="test_id",
        type=EventType.MOTION,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
    )

    with pytest.raises(ValueError):
        async_generate_event_video_url(event)


async def test_video_bad_event_ongoing(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test generating event with bad camera ID."""

    await init_entry(hass, ufp, [camera])

    event = Event(
        api=ufp.api,
        camera_id=camera.id,
        start=fixed_now - timedelta(seconds=30),
        end=None,
        id="test_id",
        type=EventType.MOTION,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
    )

    with pytest.raises(ValueError):
        async_generate_event_video_url(event)


async def test_video_bad_perms(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test generating event with bad user permissions."""

    ufp.api.bootstrap.auth_user.all_permissions = []
    await init_entry(hass, ufp, [camera])

    event = Event(
        api=ufp.api,
        camera_id=camera.id,
        start=fixed_now - timedelta(seconds=30),
        end=fixed_now,
        id="test_id",
        type=EventType.MOTION,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
    )

    with pytest.raises(PermissionError):
        async_generate_event_video_url(event)


async def test_video_bad_nvr_id(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ufp: MockUFPFixture,
    camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test video URL with bad NVR id."""

    ufp.api.request = AsyncMock()
    await init_entry(hass, ufp, [camera])

    event = Event(
        api=ufp.api,
        camera_id=camera.id,
        start=fixed_now - timedelta(seconds=30),
        end=fixed_now,
        id="test_id",
        type=EventType.MOTION,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
    )

    url = async_generate_event_video_url(event)
    url = url.replace(ufp.api.bootstrap.nvr.id, "bad_id")

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(url))

    assert response.status == 404
    ufp.api.request.assert_not_called()


async def test_video_bad_camera_id(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ufp: MockUFPFixture,
    camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test video URL with bad camera id."""

    ufp.api.request = AsyncMock()
    await init_entry(hass, ufp, [camera])

    event = Event(
        api=ufp.api,
        camera_id=camera.id,
        start=fixed_now - timedelta(seconds=30),
        end=fixed_now,
        id="test_id",
        type=EventType.MOTION,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
    )

    url = async_generate_event_video_url(event)
    url = url.replace(camera.id, "bad_id")

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(url))

    assert response.status == 404
    ufp.api.request.assert_not_called()


async def test_video_bad_camera_perms(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ufp: MockUFPFixture,
    camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test video URL with bad camera perms."""

    ufp.api.request = AsyncMock()
    await init_entry(hass, ufp, [camera])

    event = Event(
        api=ufp.api,
        camera_id=camera.id,
        start=fixed_now - timedelta(seconds=30),
        end=fixed_now,
        id="test_id",
        type=EventType.MOTION,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
    )

    url = async_generate_event_video_url(event)

    ufp.api.bootstrap.auth_user.all_permissions = []
    ufp.api.bootstrap.auth_user._perm_cache = {}

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(url))

    assert response.status == 403
    ufp.api.request.assert_not_called()


@pytest.mark.parametrize(("start", "end"), [("test", None), (None, "test")])
async def test_video_bad_params(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ufp: MockUFPFixture,
    camera: Camera,
    fixed_now: datetime,
    start: Any,
    end: Any,
) -> None:
    """Test video URL with bad start/end params."""

    ufp.api.request = AsyncMock()
    await init_entry(hass, ufp, [camera])

    event_start = fixed_now - timedelta(seconds=30)
    event = Event(
        api=ufp.api,
        camera_id=camera.id,
        start=event_start,
        end=fixed_now,
        id="test_id",
        type=EventType.MOTION,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
    )

    url = async_generate_event_video_url(event)
    from_value = event_start if start is not None else fixed_now
    to_value = start if start is not None else end
    url = url.replace(from_value.replace(microsecond=0).isoformat(), to_value)

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(url))

    assert response.status == 400
    ufp.api.request.assert_not_called()


async def test_video_bad_video(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ufp: MockUFPFixture,
    camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test video URL with no video."""

    ufp.api.request = AsyncMock(side_effect=ClientError)
    await init_entry(hass, ufp, [camera])

    event_start = fixed_now - timedelta(seconds=30)
    event = Event(
        api=ufp.api,
        camera_id=camera.id,
        start=event_start,
        end=fixed_now,
        id="test_id",
        type=EventType.MOTION,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
    )

    url = async_generate_event_video_url(event)

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(url))

    assert response.status == 404
    ufp.api.request.assert_called_once()


async def test_video(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ufp: MockUFPFixture,
    camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test video URL with no video."""

    content = Mock()
    content.__anext__ = AsyncMock(side_effect=[b"test", b"test", StopAsyncIteration()])
    content.__aiter__ = Mock(return_value=content)

    mock_response = Mock()
    mock_response.content_length = 8
    mock_response.content.iter_chunked = Mock(return_value=content)

    ufp.api.request = AsyncMock(return_value=mock_response)
    await init_entry(hass, ufp, [camera])

    event_start = fixed_now - timedelta(seconds=30)
    event = Event(
        api=ufp.api,
        camera_id=camera.id,
        start=event_start,
        end=fixed_now,
        id="test_id",
        type=EventType.MOTION,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
    )

    url = async_generate_event_video_url(event)

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(url))
    assert await response.content.read() == b"testtest"

    assert response.status == 200
    ufp.api.request.assert_called_once()


async def test_video_entity_id(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    ufp: MockUFPFixture,
    camera: Camera,
    fixed_now: datetime,
) -> None:
    """Test video URL with no video."""

    content = Mock()
    content.__anext__ = AsyncMock(side_effect=[b"test", b"test", StopAsyncIteration()])
    content.__aiter__ = Mock(return_value=content)

    mock_response = Mock()
    mock_response.content_length = 8
    mock_response.content.iter_chunked = Mock(return_value=content)

    ufp.api.request = AsyncMock(return_value=mock_response)
    await init_entry(hass, ufp, [camera])

    event_start = fixed_now - timedelta(seconds=30)
    event = Event(
        api=ufp.api,
        camera_id=camera.id,
        start=event_start,
        end=fixed_now,
        id="test_id",
        type=EventType.MOTION,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
    )

    url = async_generate_event_video_url(event)
    url = url.replace(camera.id, "camera.test_camera_high_resolution_channel")

    http_client = await hass_client()
    response = cast(ClientResponse, await http_client.get(url))
    assert await response.content.read() == b"testtest"

    assert response.status == 200
    ufp.api.request.assert_called_once()
