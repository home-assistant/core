"""Tests for unifiprotect.media_source."""

from datetime import datetime, timedelta
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pyunifiprotect.data import (
    Bootstrap,
    Camera,
    Event,
    EventType,
    Permission,
    SmartDetectObjectType,
)
from pyunifiprotect.exceptions import NvrError

from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import MediaSourceItem
from homeassistant.components.unifiprotect.const import DOMAIN
from homeassistant.components.unifiprotect.media_source import (
    ProtectMediaSource,
    async_get_media_source,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import MockUFPFixture
from .utils import init_entry

from tests.common import MockConfigEntry


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
        "test_id",
    ],
)
async def test_resolve_media_bad_identifier(
    hass: HomeAssistant, ufp: MockUFPFixture, identifier: str
) -> None:
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
) -> None:
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
) -> None:
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


@pytest.mark.parametrize(
    "identifier",
    [
        "bad_id:event:test_id",
        "test_id",
        "test_id:bad_type",
        "test_id:browse:all:all:bad_type",
        "test_id:browse:all:bad_event",
        "test_id:browse:all:all:recent",
        "test_id:browse:all:all:recent:not_a_num",
        "test_id:browse:all:all:range",
        "test_id:browse:all:all:range:not_a_num",
        "test_id:browse:all:all:range:2022:not_a_num",
        "test_id:browse:all:all:range:2022:1:not_a_num",
        "test_id:browse:all:all:range:2022:1:50",
        "test_id:browse:all:all:invalid",
        "test_id:event:bad_event_id",
        "test_id:browse:bad_camera_id",
    ],
)
async def test_browse_media_bad_identifier(
    hass: HomeAssistant, ufp: MockUFPFixture, identifier: str
) -> None:
    """Test browsing media with bad identifiers."""

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    ufp.api.get_event = AsyncMock(side_effect=NvrError)
    await init_entry(hass, ufp, [], regenerate_ids=False)

    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, identifier, None)
    with pytest.raises(BrowseError):
        await source.async_browse_media(media_item)


async def test_browse_media_event_ongoing(
    hass: HomeAssistant, ufp: MockUFPFixture, fixed_now: datetime, doorbell: Camera
) -> None:
    """Test browsing event that is still ongoing."""

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    event = Event(
        id="test_event_id",
        type=EventType.MOTION,
        start=fixed_now - timedelta(seconds=20),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
    )
    event._api = ufp.api
    ufp.api.get_event = AsyncMock(return_value=event)

    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, f"test_id:event:{event.id}", None)
    with pytest.raises(BrowseError):
        await source.async_browse_media(media_item)


async def test_browse_media_root_multiple_consoles(
    hass: HomeAssistant, ufp: MockUFPFixture, bootstrap: Bootstrap
) -> None:
    """Test browsing root level media with multiple consoles."""

    ufp.api.bootstrap._has_media = True

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    bootstrap2 = bootstrap.copy()
    bootstrap2._has_media = True
    bootstrap2.nvr = bootstrap.nvr.copy()
    bootstrap2.nvr.id = "test_id2"
    bootstrap2.nvr.mac = "A2E00C826924"
    bootstrap2.nvr.name = "UnifiProtect2"

    api2 = Mock()
    bootstrap2.nvr._api = api2
    bootstrap2._api = api2

    api2.bootstrap = bootstrap2
    api2._bootstrap = bootstrap2
    api2.api_path = "/api"
    api2.base_url = "https://127.0.0.2"
    api2.connection_host = IPv4Address("127.0.0.2")
    api2.get_bootstrap = AsyncMock(return_value=bootstrap2)
    api2.get_nvr = AsyncMock(return_value=bootstrap2.nvr)
    api2.update = AsyncMock(return_value=bootstrap2)
    api2.async_disconnect_ws = AsyncMock()

    with patch(
        "homeassistant.components.unifiprotect.utils.ProtectApiClient"
    ) as mock_api:
        mock_config = MockConfigEntry(
            domain=DOMAIN,
            data={
                "host": "1.1.1.2",
                "username": "test-username",
                "password": "test-password",
                "id": "UnifiProtect2",
                "port": 443,
                "verify_ssl": False,
            },
            version=2,
        )
        mock_config.add_to_hass(hass)

        mock_api.return_value = api2

        await hass.config_entries.async_setup(mock_config.entry_id)
        await hass.async_block_till_done()

    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, None, None)

    browse = await source.async_browse_media(media_item)

    assert browse.title == "UniFi Protect"
    assert len(browse.children) == 2
    assert browse.children[0].title.startswith("UnifiProtect")
    assert browse.children[0].identifier.startswith("test_id")
    assert browse.children[1].title.startswith("UnifiProtect")
    assert browse.children[0].identifier.startswith("test_id")


async def test_browse_media_root_multiple_consoles_only_one_media(
    hass: HomeAssistant, ufp: MockUFPFixture, bootstrap: Bootstrap
) -> None:
    """Test browsing root level media with multiple consoles."""

    ufp.api.bootstrap._has_media = True

    await hass.config_entries.async_setup(ufp.entry.entry_id)
    await hass.async_block_till_done()

    bootstrap2 = bootstrap.copy()
    bootstrap2._has_media = False
    bootstrap2.nvr = bootstrap.nvr.copy()
    bootstrap2.nvr.id = "test_id2"
    bootstrap2.nvr.mac = "A2E00C826924"
    bootstrap2.nvr.name = "UnifiProtect2"

    api2 = Mock()
    bootstrap2.nvr._api = api2
    bootstrap2._api = api2

    api2.bootstrap = bootstrap2
    api2._bootstrap = bootstrap2
    api2.api_path = "/api"
    api2.base_url = "https://127.0.0.2"
    api2.connection_host = IPv4Address("127.0.0.2")
    api2.get_nvr = AsyncMock(return_value=bootstrap2.nvr)
    api2.update = AsyncMock(return_value=bootstrap2)
    api2.async_disconnect_ws = AsyncMock()

    with patch(
        "homeassistant.components.unifiprotect.utils.ProtectApiClient"
    ) as mock_api:
        mock_config = MockConfigEntry(
            domain=DOMAIN,
            data={
                "host": "1.1.1.2",
                "username": "test-username",
                "password": "test-password",
                "id": "UnifiProtect2",
                "port": 443,
                "verify_ssl": False,
            },
            version=2,
        )
        mock_config.add_to_hass(hass)

        mock_api.return_value = api2

        await hass.config_entries.async_setup(mock_config.entry_id)
        await hass.async_block_till_done()

    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, None, None)

    browse = await source.async_browse_media(media_item)

    assert browse.title == "UnifiProtect"
    assert browse.identifier == "test_id:browse"
    assert len(browse.children) == 1
    assert browse.children[0].title == "All Cameras"
    assert browse.children[0].identifier == "test_id:browse:all"


async def test_browse_media_root_single_console(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test browsing root level media with a single console."""

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, None, None)

    browse = await source.async_browse_media(media_item)

    assert browse.title == "UnifiProtect"
    assert browse.identifier == "test_id:browse"
    assert len(browse.children) == 2
    assert browse.children[0].title == "All Cameras"
    assert browse.children[0].identifier == "test_id:browse:all"
    assert browse.children[1].title == doorbell.name
    assert browse.children[1].identifier == f"test_id:browse:{doorbell.id}"
    assert browse.children[1].thumbnail is not None


async def test_browse_media_camera(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
    camera: Camera,
) -> None:
    """Test browsing camera selector level media."""

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [doorbell, camera])

    ufp.api.bootstrap.auth_user.all_permissions = [
        Permission.unifi_dict_to_dict(
            {"rawPermission": "camera:create,read,write,delete,deletemedia:*"}
        ),
        Permission.unifi_dict_to_dict(
            {"rawPermission": f"camera:readmedia:{doorbell.id}"}
        ),
    ]

    entity_registry.async_update_entity(
        "camera.test_camera_high_resolution_channel",
        disabled_by=er.RegistryEntryDisabler("user"),
    )
    await hass.async_block_till_done()

    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, "test_id:browse", None)

    browse = await source.async_browse_media(media_item)

    assert browse.title == "UnifiProtect"
    assert browse.identifier == "test_id:browse"
    assert len(browse.children) == 2
    assert browse.children[0].title == "All Cameras"
    assert browse.children[0].identifier == "test_id:browse:all"
    assert browse.children[1].title == doorbell.name
    assert browse.children[1].identifier == f"test_id:browse:{doorbell.id}"
    assert browse.children[1].thumbnail is None


async def test_browse_media_camera_offline(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test browsing camera selector level media when camera is offline."""

    doorbell.is_connected = False

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [doorbell])

    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, "test_id:browse", None)

    browse = await source.async_browse_media(media_item)

    assert browse.title == "UnifiProtect"
    assert browse.identifier == "test_id:browse"
    assert len(browse.children) == 2
    assert browse.children[0].title == "All Cameras"
    assert browse.children[0].identifier == "test_id:browse:all"
    assert browse.children[1].title == doorbell.name
    assert browse.children[1].identifier == f"test_id:browse:{doorbell.id}"
    assert browse.children[1].thumbnail is None


async def test_browse_media_event_type(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test browsing event type selector level media."""

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, "test_id:browse:all", None)

    browse = await source.async_browse_media(media_item)

    assert browse.title == "UnifiProtect > All Cameras"
    assert browse.identifier == "test_id:browse:all"
    assert len(browse.children) == 5
    assert browse.children[0].title == "All Events"
    assert browse.children[0].identifier == "test_id:browse:all:all"
    assert browse.children[1].title == "Ring Events"
    assert browse.children[1].identifier == "test_id:browse:all:ring"
    assert browse.children[2].title == "Motion Events"
    assert browse.children[2].identifier == "test_id:browse:all:motion"
    assert browse.children[3].title == "Object Detections"
    assert browse.children[3].identifier == "test_id:browse:all:smart"
    assert browse.children[4].title == "Audio Detections"
    assert browse.children[4].identifier == "test_id:browse:all:audio"


ONE_MONTH_SIMPLE = (
    datetime(
        year=2022,
        month=9,
        day=1,
        hour=3,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=dt_util.get_time_zone("US/Pacific"),
    ),
    1,
)
TWO_MONTH_SIMPLE = (
    datetime(
        year=2022,
        month=8,
        day=31,
        hour=3,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=dt_util.get_time_zone("US/Pacific"),
    ),
    2,
)


@pytest.mark.parametrize(
    ("start", "months"),
    [ONE_MONTH_SIMPLE, TWO_MONTH_SIMPLE],
)
@pytest.mark.freeze_time("2022-09-15 03:00:00-07:00")
async def test_browse_media_time(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    start: datetime,
    months: int,
) -> None:
    """Test browsing time selector level media."""

    end = datetime.fromisoformat("2022-09-15 03:00:00-07:00")
    end_local = dt_util.as_local(end)

    ufp.api.bootstrap._recording_start = dt_util.as_utc(start)

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    base_id = f"test_id:browse:{doorbell.id}:all"
    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, base_id, None)

    browse = await source.async_browse_media(media_item)

    assert browse.title == f"UnifiProtect > {doorbell.name} > All Events"
    assert browse.identifier == base_id
    assert len(browse.children) == 3 + months
    assert browse.children[0].title == "Last 24 Hours"
    assert browse.children[0].identifier == f"{base_id}:recent:1"
    assert browse.children[1].title == "Last 7 Days"
    assert browse.children[1].identifier == f"{base_id}:recent:7"
    assert browse.children[2].title == "Last 30 Days"
    assert browse.children[2].identifier == f"{base_id}:recent:30"
    assert browse.children[3].title == f"{end_local.strftime('%B %Y')}"
    assert (
        browse.children[3].identifier
        == f"{base_id}:range:{end_local.year}:{end_local.month}"
    )


ONE_MONTH_TIMEZONE = (
    datetime(
        year=2022,
        month=8,
        day=1,
        hour=3,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=dt_util.get_time_zone("US/Pacific"),
    ),
    1,
)
TWO_MONTH_TIMEZONE = (
    datetime(
        year=2022,
        month=7,
        day=31,
        hour=21,
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=dt_util.get_time_zone("US/Pacific"),
    ),
    2,
)


@pytest.mark.parametrize(
    ("start", "months"),
    [ONE_MONTH_TIMEZONE, TWO_MONTH_TIMEZONE],
)
@pytest.mark.freeze_time("2022-08-31 21:00:00-07:00")
async def test_browse_media_time_timezone(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    start: datetime,
    months: int,
) -> None:
    """Test browsing time selector level media."""

    end = datetime.fromisoformat("2022-08-31 21:00:00-07:00")
    end_local = dt_util.as_local(end)

    ufp.api.bootstrap._recording_start = dt_util.as_utc(start)

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    base_id = f"test_id:browse:{doorbell.id}:all"
    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, base_id, None)

    browse = await source.async_browse_media(media_item)

    assert browse.title == f"UnifiProtect > {doorbell.name} > All Events"
    assert browse.identifier == base_id
    assert len(browse.children) == 3 + months
    assert browse.children[0].title == "Last 24 Hours"
    assert browse.children[0].identifier == f"{base_id}:recent:1"
    assert browse.children[1].title == "Last 7 Days"
    assert browse.children[1].identifier == f"{base_id}:recent:7"
    assert browse.children[2].title == "Last 30 Days"
    assert browse.children[2].identifier == f"{base_id}:recent:30"
    assert browse.children[3].title == f"{end_local.strftime('%B %Y')}"
    assert (
        browse.children[3].identifier
        == f"{base_id}:range:{end_local.year}:{end_local.month}"
    )


async def test_browse_media_recent(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, fixed_now: datetime
) -> None:
    """Test browsing event selector level media for recent days."""

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
    ufp.api.get_events_raw = AsyncMock(return_value=[event.unifi_dict()])

    base_id = f"test_id:browse:{doorbell.id}:motion:recent:1"
    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, base_id, None)

    browse = await source.async_browse_media(media_item)

    assert (
        browse.title
        == f"UnifiProtect > {doorbell.name} > Motion Events > Last 24 Hours (1)"
    )
    assert browse.identifier == base_id
    assert len(browse.children) == 1
    assert browse.children[0].identifier == "test_id:event:test_event_id"


async def test_browse_media_recent_truncated(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, fixed_now: datetime
) -> None:
    """Test browsing event selector level media for recent days."""
    hass.config_entries.async_update_entry(ufp.entry, options={"max_media": 1})

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
    ufp.api.get_events_raw = AsyncMock(return_value=[event.unifi_dict()])

    base_id = f"test_id:browse:{doorbell.id}:motion:recent:1"
    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, base_id, None)

    browse = await source.async_browse_media(media_item)

    assert (
        browse.title
        == f"UnifiProtect > {doorbell.name} > Motion Events > Last 24 Hours (1 TRUNCATED)"
    )
    assert browse.identifier == base_id
    assert len(browse.children) == 1
    assert browse.children[0].identifier == "test_id:event:test_event_id"


@pytest.mark.parametrize(
    ("event", "expected_title"),
    [
        (
            Event(
                id="test_event_id",
                type=EventType.RING,
                start=datetime(1000, 1, 1, 0, 0, 0),
                end=None,
                score=100,
                smart_detect_types=[],
                smart_detect_event_ids=[],
                camera_id="test",
            ),
            "Ring Event",
        ),
        (
            Event(
                id="test_event_id",
                type=EventType.MOTION,
                start=datetime(1000, 1, 1, 0, 0, 0),
                end=None,
                score=100,
                smart_detect_types=[],
                smart_detect_event_ids=[],
                camera_id="test",
            ),
            "Motion Event",
        ),
        (
            Event(
                id="test_event_id",
                type=EventType.SMART_DETECT,
                start=datetime(1000, 1, 1, 0, 0, 0),
                end=None,
                score=100,
                smart_detect_types=["person"],
                smart_detect_event_ids=[],
                camera_id="test",
                metadata={
                    "detected_thumbnails": [
                        {
                            "clock_best_wall": datetime(1000, 1, 1, 0, 0, 0),
                            "type": "person",
                            "cropped_id": "event_id",
                        }
                    ],
                },
            ),
            "Object Detection - Person",
        ),
        (
            Event(
                id="test_event_id",
                type=EventType.SMART_DETECT,
                start=datetime(1000, 1, 1, 0, 0, 0),
                end=None,
                score=100,
                smart_detect_types=["vehicle", "person"],
                smart_detect_event_ids=[],
                camera_id="test",
            ),
            "Object Detection - Person, Vehicle",
        ),
        (
            Event(
                id="test_event_id",
                type=EventType.SMART_DETECT,
                start=datetime(1000, 1, 1, 0, 0, 0),
                end=None,
                score=100,
                smart_detect_types=["vehicle", "licensePlate"],
                smart_detect_event_ids=[],
                camera_id="test",
            ),
            "Object Detection - License Plate, Vehicle",
        ),
        (
            Event(
                id="test_event_id",
                type=EventType.SMART_DETECT,
                start=datetime(1000, 1, 1, 0, 0, 0),
                end=None,
                score=100,
                smart_detect_types=["vehicle", "licensePlate"],
                smart_detect_event_ids=[],
                camera_id="test",
                metadata={
                    "license_plate": {"name": "ABC1234", "confidence_level": 95},
                    "detected_thumbnails": [
                        {
                            "clock_best_wall": datetime(1000, 1, 1, 0, 0, 0),
                            "type": "vehicle",
                            "cropped_id": "event_id",
                        }
                    ],
                },
            ),
            "Object Detection - Vehicle: ABC1234",
        ),
        (
            Event(
                id="test_event_id",
                type=EventType.SMART_DETECT,
                start=datetime(1000, 1, 1, 0, 0, 0),
                end=None,
                score=100,
                smart_detect_types=["vehicle", "licensePlate"],
                smart_detect_event_ids=[],
                camera_id="test",
                metadata={
                    "license_plate": {"name": "ABC1234", "confidence_level": 95},
                    "detected_thumbnails": [
                        {
                            "clock_best_wall": datetime(1000, 1, 1, 0, 0, 0),
                            "type": "vehicle",
                            "cropped_id": "event_id",
                            "attributes": {
                                "vehicle_type": {
                                    "val": "car",
                                    "confidence": 95,
                                }
                            },
                        }
                    ],
                },
            ),
            "Object Detection - Car: ABC1234",
        ),
        (
            Event(
                id="test_event_id",
                type=EventType.SMART_DETECT,
                start=datetime(1000, 1, 1, 0, 0, 0),
                end=None,
                score=100,
                smart_detect_types=["vehicle", "licensePlate"],
                smart_detect_event_ids=[],
                camera_id="test",
                metadata={
                    "license_plate": {"name": "ABC1234", "confidence_level": 95},
                    "detected_thumbnails": [
                        {
                            "clock_best_wall": datetime(1000, 1, 1, 0, 0, 0),
                            "type": "vehicle",
                            "cropped_id": "event_id",
                            "attributes": {
                                "color": {
                                    "val": "black",
                                    "confidence": 95,
                                }
                            },
                        },
                        {
                            "clock_best_wall": datetime(1000, 1, 1, 0, 0, 0),
                            "type": "person",
                            "cropped_id": "event_id",
                        },
                    ],
                },
            ),
            "Object Detection - Black Vehicle: ABC1234",
        ),
        (
            Event(
                id="test_event_id",
                type=EventType.SMART_DETECT,
                start=datetime(1000, 1, 1, 0, 0, 0),
                end=None,
                score=100,
                smart_detect_types=["vehicle"],
                smart_detect_event_ids=[],
                camera_id="test",
                metadata={
                    "detected_thumbnails": [
                        {
                            "clock_best_wall": datetime(1000, 1, 1, 0, 0, 0),
                            "type": "vehicle",
                            "cropped_id": "event_id",
                            "attributes": {
                                "color": {
                                    "val": "black",
                                    "confidence": 95,
                                },
                                "vehicle_type": {
                                    "val": "car",
                                    "confidence": 95,
                                },
                            },
                        }
                    ]
                },
            ),
            "Object Detection - Black Car",
        ),
        (
            Event(
                id="test_event_id",
                type=EventType.SMART_AUDIO_DETECT,
                start=datetime(1000, 1, 1, 0, 0, 0),
                end=None,
                score=100,
                smart_detect_types=["alrmSpeak"],
                smart_detect_event_ids=[],
                camera_id="test",
            ),
            "Audio Detection - Speak",
        ),
    ],
)
async def test_browse_media_event(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    fixed_now: datetime,
    event: Event,
    expected_title: str,
) -> None:
    """Test browsing specific event."""

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    event.start = fixed_now - timedelta(seconds=20)
    event.end = fixed_now
    event.camera_id = doorbell.id
    event._api = ufp.api
    ufp.api.get_event = AsyncMock(return_value=event)

    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, "test_id:event:test_event_id", None)

    browse = await source.async_browse_media(media_item)
    # chop off the datetime/duration
    title = " ".join(browse.title.split(" ")[3:])

    assert browse.identifier == "test_id:event:test_event_id"
    assert browse.children is None
    assert browse.media_class == MediaClass.VIDEO
    assert title == expected_title


async def test_browse_media_eventthumb(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, fixed_now: datetime
) -> None:
    """Test browsing specific event."""

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    event = Event(
        id="test_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=20),
        end=fixed_now,
        score=100,
        smart_detect_types=[SmartDetectObjectType.PERSON],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
    )
    event._api = ufp.api
    ufp.api.get_event = AsyncMock(return_value=event)

    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, "test_id:eventthumb:test_event_id", None)

    browse = await source.async_browse_media(media_item)

    assert browse.identifier == "test_id:eventthumb:test_event_id"
    assert browse.children is None
    assert browse.media_class == MediaClass.IMAGE


@pytest.mark.freeze_time("2022-09-15 03:00:00-07:00")
async def test_browse_media_day(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test browsing day selector level media."""

    start = datetime.fromisoformat("2022-09-03 03:00:00-07:00")
    end = datetime.fromisoformat("2022-09-15 03:00:00-07:00")
    ufp.api.bootstrap._recording_start = dt_util.as_utc(start)

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    base_id = f"test_id:browse:{doorbell.id}:all:range:{end.year}:{end.month}"
    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, base_id, None)

    browse = await source.async_browse_media(media_item)

    assert (
        browse.title
        == f"UnifiProtect > {doorbell.name} > All Events > {end.strftime('%B %Y')}"
    )
    assert browse.identifier == base_id
    assert len(browse.children) == 14
    assert browse.children[0].title == "Whole Month"
    assert browse.children[0].identifier == f"{base_id}:all"


async def test_browse_media_browse_day(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, fixed_now: datetime
) -> None:
    """Test events for a specific day."""

    last_month = fixed_now.replace(day=1) - timedelta(days=1)
    ufp.api.bootstrap._recording_start = last_month

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
    ufp.api.get_events_raw = AsyncMock(return_value=[event.unifi_dict()])

    base_id = f"test_id:browse:{doorbell.id}:motion:range:{fixed_now.year}:{fixed_now.month}:1"
    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, base_id, None)

    browse = await source.async_browse_media(media_item)

    start = fixed_now.replace(day=1)
    assert (
        browse.title
        == f"UnifiProtect > {doorbell.name} > Motion Events > {fixed_now.strftime('%B %Y')} > {start.strftime('%x')} (1)"
    )
    assert browse.identifier == base_id
    assert len(browse.children) == 1
    assert browse.children[0].identifier == "test_id:event:test_event_id"


async def test_browse_media_browse_whole_month(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, fixed_now: datetime
) -> None:
    """Test events for a specific day."""

    fixed_now = fixed_now.replace(month=10)
    last_month = fixed_now.replace(day=1) - timedelta(days=1)
    ufp.api.bootstrap._recording_start = last_month

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
    ufp.api.get_events_raw = AsyncMock(return_value=[event.unifi_dict()])

    base_id = (
        f"test_id:browse:{doorbell.id}:all:range:{fixed_now.year}:{fixed_now.month}:all"
    )
    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, base_id, None)

    browse = await source.async_browse_media(media_item)

    assert (
        browse.title
        == f"UnifiProtect > {doorbell.name} > All Events > {fixed_now.strftime('%B %Y')} > Whole Month (1)"
    )
    assert browse.identifier == base_id
    assert len(browse.children) == 1
    assert browse.children[0].identifier == "test_id:event:test_event_id"


async def test_browse_media_browse_whole_month_december(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, fixed_now: datetime
) -> None:
    """Test events for a specific day."""

    fixed_now = fixed_now.replace(month=12)
    last_month = fixed_now.replace(day=1) - timedelta(days=1)
    ufp.api.bootstrap._recording_start = last_month

    ufp.api.get_bootstrap = AsyncMock(return_value=ufp.api.bootstrap)
    await init_entry(hass, ufp, [doorbell], regenerate_ids=False)

    event1 = Event(
        id="test_event_id",
        type=EventType.SMART_DETECT,
        start=fixed_now - timedelta(seconds=3663),
        end=fixed_now,
        score=100,
        smart_detect_types=[SmartDetectObjectType.PERSON],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
    )
    event1._api = ufp.api
    event2 = Event(
        id="test_event_id2",
        type=EventType.MOTION,
        start=fixed_now - timedelta(seconds=20),
        end=fixed_now,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=["test_event_id"],
        camera_id=doorbell.id,
    )
    event2._api = ufp.api
    event3 = Event(
        id="test_event_id3",
        type=EventType.MOTION,
        start=fixed_now - timedelta(seconds=20),
        end=fixed_now,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id="other_camera",
    )
    event3._api = ufp.api
    event4 = Event(
        id="test_event_id4",
        type=EventType.MOTION,
        start=fixed_now - timedelta(seconds=20),
        end=None,
        score=100,
        smart_detect_types=[],
        smart_detect_event_ids=[],
        camera_id=doorbell.id,
    )
    event4._api = ufp.api

    ufp.api.get_events_raw = AsyncMock(
        return_value=[
            event1.unifi_dict(),
            event2.unifi_dict(),
            event3.unifi_dict(),
            event4.unifi_dict(),
        ]
    )

    base_id = (
        f"test_id:browse:{doorbell.id}:all:range:{fixed_now.year}:{fixed_now.month}:all"
    )
    source = await async_get_media_source(hass)
    media_item = MediaSourceItem(hass, DOMAIN, base_id, None)

    browse = await source.async_browse_media(media_item)

    assert (
        browse.title
        == f"UnifiProtect > {doorbell.name} > All Events > {fixed_now.strftime('%B %Y')} > Whole Month (1)"
    )
    assert browse.identifier == base_id
    assert len(browse.children) == 1
    assert browse.children[0].identifier == "test_id:event:test_event_id"
