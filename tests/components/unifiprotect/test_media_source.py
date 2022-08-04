"""Tests for unifiprotect.media_source."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from pyunifiprotect.data import Camera, Event, EventType
from pyunifiprotect.exceptions import NvrError

from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source import MediaSourceItem
from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.components.unifiprotect.media_source import (
    ProtectMediaSource,
    async_get_media_source,
)
from homeassistant.core import HomeAssistant

from .conftest import MockUFPFixture
from .utils import init_entry


async def test_get_media_source(hass: HomeAssistant) -> None:
    """Test the async_get_media_source function and ProtectMediaSource constructor."""
    source = await async_get_media_source(hass)
    assert isinstance(source, ProtectMediaSource)
    assert source.domain == DOMAIN


@pytest.mark.parametrize(
    "identifier",
    [
        "test_id:bad_type:test_id",
        "bad_id:event:test_id",
        "test_id:event:bad_id",
    ],
)
async def test_resolve_media_bad_identifier(
    hass: HomeAssistant, ufp: MockUFPFixture, identifier: str
):
    """Test resolving bad identifiers."""

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    ufp.api.get_event = AsyncMock(side_effect=NvrError)
    await init_entry(hass, ufp, [], regenerate_ids=False)

    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, identifier, None)
    with pytest.raises(BrowseError):
        await source.async_resolve_media(media_item)


async def test_resolve_media_thumbnail(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, fixed_now: datetime
):
    """Test resolving event thumbnails."""

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    event = Event(
        id="test_event_id",
        type=EventType.MOTION,
        start=fixed_now - timedelta(seconds=20),
        end=fixed_now,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
    )
    event._api = ufp.api
    ufp.api.bootstrap.events = {"test_event_id": event}

    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, "test_id:eventthumb:test_event_id", None)
    play_media = await source.async_resolve_media(media_item)

    assert play_media.mime_type == "image/jpeg"
    assert play_media.url.startswith(
        "/api/unifiprotect/thumbnail/test_id/test_event_id"
    )


async def test_resolve_media_event(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, fixed_now: datetime
):
    """Test resolving event clips."""

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    event = Event(
        id="test_event_id",
        type=EventType.MOTION,
        start=fixed_now - timedelta(seconds=20),
        end=fixed_now,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
    )
    event._api = ufp.api
    ufp.api.get_event = AsyncMock(return_value=event)

    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, "test_id:event:test_event_id", None)
    play_media = await source.async_resolve_media(media_item)

    start = event.start.replace(microsecond=0).isoformat()
    end = event.end.replace(microsecond=0).isoformat()

    assert play_media.mime_type == "video/mp4"
    assert play_media.url.startswith(
        f"/api/unifiprotect/video/test_id/{event.camera_id}/{start}/{end}"
    )
