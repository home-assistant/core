"""Tests for query-shaped RPCs — service-path responses + ``EntityQuery``.

Two layers are covered:

* **Round-trip rebuild helpers** — the highest-risk part (the
  ``as_dict``-vs-constructor asymmetry). Each rich type is serialised with its
  own serialiser and rebuilt with the proxy's helper; the re-serialised result
  must match, with no wire/Struct in the loop.
* **Proxy behaviour** — a wired bridge + in-memory channel pair, a stub
  sandbox-side handler, and an assertion that the proxy returns the rebuilt
  typed object (or surfaces the translated error).
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
from typing import Any

import pytest

from homeassistant.components.calendar import CalendarEvent
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    SearchMedia,
    SearchMediaQuery,
)
from homeassistant.components.sandbox._proto import sandbox_pb2 as pb
from homeassistant.components.sandbox.bridge import SandboxBridge
from homeassistant.components.sandbox.channel import Channel
from homeassistant.components.sandbox.entity.calendar import _calendar_event_from_dict
from homeassistant.components.sandbox.entity.media_player import (
    _browse_media_from_dict,
    _search_media_from_dict,
)
from homeassistant.components.sandbox.entity.vacuum import _segment_from_dict
from homeassistant.components.sandbox.messages import (
    dict_to_struct,
    make_entity_description,
    struct_to_dict,
)
from homeassistant.components.vacuum import Segment
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from ._helpers import make_channel_pair

from tests.common import MockConfigEntry


async def _wire(hass: HomeAssistant) -> tuple[SandboxBridge, Channel, Channel]:
    """Return a bridge + main + sandbox in-memory channels."""
    main_channel, sandbox_channel = make_channel_pair(name_a="main", name_b="sandbox")
    bridge = SandboxBridge(hass, group="built-in", channel=main_channel)
    main_channel.start()
    sandbox_channel.start()
    return bridge, main_channel, sandbox_channel


@pytest.fixture(name="entry")
def _entry_fixture(hass: HomeAssistant) -> ConfigEntry:
    """Mock ConfigEntry the synthetic proxy entities attach to."""
    entry = MockConfigEntry(domain="sandbox_synthetic", title="Synthetic", data={})
    entry.add_to_hass(hass)
    return entry


async def _register(
    bridge: SandboxBridge,
    sandbox_channel: Channel,
    entry: ConfigEntry,
    domain: str,
    sandbox_entity_id: str,
    *,
    supported_features: int = 0,
    capabilities: dict[str, Any] | None = None,
    state: str = "on",
) -> Any:
    """Register a synthetic proxy entity and let its initial state settle."""
    payload = make_entity_description(
        entry_id=entry.entry_id,
        domain=domain,
        sandbox_entity_id=sandbox_entity_id,
        unique_id=f"sandbox-{domain}",
        supported_features=supported_features,
        capabilities=capabilities or {},
        initial_state=state,
    )
    await sandbox_channel.call("sandbox/register_entity", payload)
    for _ in range(20):
        await asyncio.sleep(0)
    return bridge._entities[sandbox_entity_id]


# --- Round-trip rebuild helpers (no wire) ---------------------------------


@pytest.mark.parametrize(
    "event",
    [
        pytest.param(
            CalendarEvent(
                start=datetime.datetime(2026, 5, 23, 10, 0, tzinfo=datetime.UTC),
                end=datetime.datetime(2026, 5, 23, 11, 0, tzinfo=datetime.UTC),
                summary="Lunch",
                description="With the team",
                location="Cafe",
            ),
            id="timed",
        ),
        pytest.param(
            CalendarEvent(
                start=datetime.date(2026, 5, 23),
                end=datetime.date(2026, 5, 24),
                summary="Holiday",
            ),
            id="all_day",
        ),
        pytest.param(
            CalendarEvent(
                start=datetime.datetime(2026, 5, 23, 9, 0, tzinfo=datetime.UTC),
                end=datetime.datetime(2026, 5, 23, 9, 30, tzinfo=datetime.UTC),
                summary="Standup",
                uid="abc-123",
                recurrence_id="20260523T090000",
                rrule="FREQ=DAILY",
            ),
            id="recurring",
        ),
    ],
)
def test_calendar_event_round_trip(event: CalendarEvent) -> None:
    """A ``CalendarEvent`` survives ``as_dict`` → rebuild → ``as_dict``."""
    rebuilt = _calendar_event_from_dict(event.as_dict())
    assert rebuilt.as_dict() == event.as_dict()
    assert rebuilt.all_day == event.all_day


def test_browse_media_round_trip() -> None:
    """A recursive ``BrowseMedia`` survives ``as_dict`` → rebuild → ``as_dict``."""
    child = BrowseMedia(
        media_class=MediaClass.MUSIC,
        media_content_id="track/1",
        media_content_type="music",
        title="Song",
        can_play=True,
        can_expand=False,
        thumbnail="http://example.test/art.png",
    )
    root = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="library",
        media_content_type="library",
        title="Library",
        can_play=False,
        can_expand=True,
        children=[child],
        not_shown=3,
        can_search=True,
    )
    rebuilt = _browse_media_from_dict(root.as_dict())
    assert rebuilt.as_dict() == root.as_dict()
    assert rebuilt.children is not None
    assert rebuilt.children[0].title == "Song"


# --- Service-path proxy behaviour -----------------------------------------


async def test_calendar_get_events_proxy(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """``async_get_events`` forwards ``calendar.get_events`` and rebuilds."""
    bridge, main_channel, sandbox_channel = await _wire(hass)
    sandbox_entity_id = "calendar.synthetic"
    captured: list[pb.CallService] = []
    event_dict = {
        "start": "2026-05-23T10:00:00+00:00",
        "end": "2026-05-23T11:00:00+00:00",
        "summary": "Lunch",
    }

    async def _on_call(payload: pb.CallService) -> pb.CallServiceResult:
        captured.append(payload)
        result = pb.CallServiceResult()
        result.response.data.CopyFrom(
            dict_to_struct({sandbox_entity_id: {"events": [event_dict]}})
        )
        return result

    sandbox_channel.register("sandbox/call_service", _on_call)
    start = datetime.datetime(2026, 5, 23, 9, 0, tzinfo=datetime.UTC)
    end = datetime.datetime(2026, 5, 23, 12, 0, tzinfo=datetime.UTC)
    try:
        proxy = await _register(
            bridge, sandbox_channel, entry, "calendar", sandbox_entity_id
        )
        events = await proxy.async_get_events(hass, start, end)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert len(events) == 1
    assert events[0].summary == "Lunch"
    assert captured[0].service == "get_events"
    assert captured[0].return_response is True
    data = struct_to_dict(captured[0].service_data)
    assert data["start_date_time"] == start.isoformat()
    assert data["end_date_time"] == end.isoformat()


@pytest.mark.parametrize(
    ("method", "forecast_type"),
    [
        ("async_forecast_daily", "daily"),
        ("async_forecast_hourly", "hourly"),
        ("async_forecast_twice_daily", "twice_daily"),
    ],
)
async def test_weather_forecast_proxy(
    hass: HomeAssistant,
    entry: ConfigEntry,
    method: str,
    forecast_type: str,
) -> None:
    """Each ``async_forecast_*`` forwards ``weather.get_forecasts``."""
    bridge, main_channel, sandbox_channel = await _wire(hass)
    sandbox_entity_id = "weather.synthetic"
    captured: list[pb.CallService] = []
    forecast = [
        {
            "datetime": "2026-05-23T00:00:00+00:00",
            "temperature": 20.0,
            "condition": "sunny",
        }
    ]

    async def _on_call(payload: pb.CallService) -> pb.CallServiceResult:
        captured.append(payload)
        result = pb.CallServiceResult()
        result.response.data.CopyFrom(
            dict_to_struct({sandbox_entity_id: {"forecast": forecast}})
        )
        return result

    sandbox_channel.register("sandbox/call_service", _on_call)
    try:
        proxy = await _register(
            bridge, sandbox_channel, entry, "weather", sandbox_entity_id
        )
        result = await getattr(proxy, method)()
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result == forecast
    assert captured[0].service == "get_forecasts"
    assert struct_to_dict(captured[0].service_data) == {"type": forecast_type}


async def test_browse_media_proxy(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """``async_browse_media`` forwards the service and rebuilds ``BrowseMedia``."""
    bridge, main_channel, sandbox_channel = await _wire(hass)
    sandbox_entity_id = "media_player.synthetic"
    captured: list[pb.CallService] = []
    browse = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="root",
        media_content_type="library",
        title="Library",
        can_play=False,
        can_expand=True,
        children=[
            BrowseMedia(
                media_class=MediaClass.MUSIC,
                media_content_id="track/1",
                media_content_type="music",
                title="Song",
                can_play=True,
                can_expand=False,
            )
        ],
    ).as_dict()

    async def _on_call(payload: pb.CallService) -> pb.CallServiceResult:
        captured.append(payload)
        result = pb.CallServiceResult()
        result.response.data.CopyFrom(dict_to_struct({sandbox_entity_id: browse}))
        return result

    sandbox_channel.register("sandbox/call_service", _on_call)
    try:
        proxy = await _register(
            bridge, sandbox_channel, entry, "media_player", sandbox_entity_id
        )
        result = await proxy.async_browse_media(
            media_content_type="library", media_content_id="root"
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert isinstance(result, BrowseMedia)
    assert result.title == "Library"
    assert result.children is not None
    assert result.children[0].title == "Song"
    assert captured[0].service == "browse_media"
    data = struct_to_dict(captured[0].service_data)
    assert data == {"media_content_type": "library", "media_content_id": "root"}


# --- EntityQuery round-trip rebuild helpers (no wire) ---------------------


def test_search_media_round_trip() -> None:
    """A ``SearchMedia`` survives ``as_dict`` → rebuild → ``as_dict``."""
    search = SearchMedia(
        result=[
            BrowseMedia(
                media_class=MediaClass.MUSIC,
                media_content_id="track/1",
                media_content_type="music",
                title="Song",
                can_play=True,
                can_expand=False,
            ),
            BrowseMedia(
                media_class=MediaClass.ALBUM,
                media_content_id="album/2",
                media_content_type="album",
                title="Record",
                can_play=True,
                can_expand=True,
            ),
        ]
    )
    rebuilt = _search_media_from_dict(search.as_dict())
    assert rebuilt.as_dict() == search.as_dict()
    assert [item.title for item in rebuilt.result] == ["Song", "Record"]


def test_segment_round_trip() -> None:
    """A ``Segment`` survives ``asdict`` → rebuild."""
    segment = Segment(id="3", name="Kitchen", group="downstairs")
    rebuilt = _segment_from_dict(dataclasses.asdict(segment))
    assert rebuilt == segment


# --- EntityQuery proxy behaviour ------------------------------------------


def _entity_query_responder(captured: list[pb.EntityQuery], value: Any) -> Any:
    """Return a stub ``sandbox/entity_query`` handler returning ``value``."""

    async def _on_query(payload: pb.EntityQuery) -> pb.EntityQueryResult:
        captured.append(payload)
        result = pb.EntityQueryResult()
        result.result.CopyFrom(dict_to_struct({"value": value}))
        return result

    return _on_query


async def test_search_media_proxy(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """``async_search_media`` forwards EntityQuery and rebuilds ``SearchMedia``."""
    bridge, main_channel, sandbox_channel = await _wire(hass)
    sandbox_entity_id = "media_player.synthetic"
    captured: list[pb.EntityQuery] = []
    value = SearchMedia(
        result=[
            BrowseMedia(
                media_class=MediaClass.MUSIC,
                media_content_id="track/1",
                media_content_type="music",
                title="Jazz Hit",
                can_play=True,
                can_expand=False,
            )
        ]
    ).as_dict()
    sandbox_channel.register(
        "sandbox/entity_query", _entity_query_responder(captured, value)
    )
    try:
        proxy = await _register(
            bridge, sandbox_channel, entry, "media_player", sandbox_entity_id
        )
        result = await proxy.async_search_media(SearchMediaQuery(search_query="jazz"))
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert isinstance(result, SearchMedia)
    assert result.result[0].title == "Jazz Hit"
    assert captured[0].method == "async_internal_search_media"
    assert struct_to_dict(captured[0].args) == {"search_query": "jazz"}


async def test_release_notes_proxy(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """``async_release_notes`` forwards EntityQuery and returns the str."""
    bridge, main_channel, sandbox_channel = await _wire(hass)
    sandbox_entity_id = "update.synthetic"
    captured: list[pb.EntityQuery] = []
    sandbox_channel.register(
        "sandbox/entity_query",
        _entity_query_responder(captured, "## 1.1\n- Fixed things"),
    )
    try:
        proxy = await _register(
            bridge, sandbox_channel, entry, "update", sandbox_entity_id
        )
        result = await proxy.async_release_notes()
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result == "## 1.1\n- Fixed things"
    assert captured[0].method == "async_release_notes"
    assert struct_to_dict(captured[0].args) == {}


async def test_get_segments_proxy(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """``async_get_segments`` forwards EntityQuery and rebuilds ``Segment``s."""
    bridge, main_channel, sandbox_channel = await _wire(hass)
    sandbox_entity_id = "vacuum.synthetic"
    captured: list[pb.EntityQuery] = []
    value = [
        {"id": "1", "name": "Kitchen", "group": "downstairs"},
        {"id": "2", "name": "Hall"},
    ]
    sandbox_channel.register(
        "sandbox/entity_query", _entity_query_responder(captured, value)
    )
    try:
        proxy = await _register(
            bridge, sandbox_channel, entry, "vacuum", sandbox_entity_id
        )
        result = await proxy.async_get_segments()
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert all(isinstance(segment, Segment) for segment in result)
    assert [segment.name for segment in result] == ["Kitchen", "Hall"]
    assert result[1].group is None
    assert captured[0].method == "async_get_segments"


@pytest.mark.parametrize(
    ("method", "args", "expected_method", "expected_args"),
    [
        (
            "async_update_event",
            ("uid-1", {"summary": "New"}),
            "async_update_event",
            {
                "uid": "uid-1",
                "event": {"summary": "New"},
                "recurrence_id": None,
                "recurrence_range": None,
            },
        ),
        (
            "async_delete_event",
            ("uid-2",),
            "async_delete_event",
            {"uid": "uid-2", "recurrence_id": None, "recurrence_range": None},
        ),
    ],
)
async def test_calendar_mutation_proxy(
    hass: HomeAssistant,
    entry: ConfigEntry,
    method: str,
    args: tuple[Any, ...],
    expected_method: str,
    expected_args: dict[str, Any],
) -> None:
    """Calendar update/delete forward through EntityQuery (None result)."""
    bridge, main_channel, sandbox_channel = await _wire(hass)
    sandbox_entity_id = "calendar.synthetic"
    captured: list[pb.EntityQuery] = []
    sandbox_channel.register(
        "sandbox/entity_query", _entity_query_responder(captured, None)
    )
    try:
        proxy = await _register(
            bridge, sandbox_channel, entry, "calendar", sandbox_entity_id
        )
        result = await getattr(proxy, method)(*args)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result is None
    assert captured[0].method == expected_method
    assert struct_to_dict(captured[0].args) == expected_args


# --- EntityQuery error paths ----------------------------------------------


async def test_entity_query_error_translates(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A sandbox-side error surfaces as a translated ``HomeAssistantError``."""
    bridge, main_channel, sandbox_channel = await _wire(hass)
    sandbox_entity_id = "update.synthetic"

    async def _on_query(payload: pb.EntityQuery) -> pb.EntityQueryResult:
        raise ServiceValidationError("nope")

    sandbox_channel.register("sandbox/entity_query", _on_query)
    try:
        proxy = await _register(
            bridge, sandbox_channel, entry, "update", sandbox_entity_id
        )
        with pytest.raises(HomeAssistantError):
            await proxy.async_release_notes()
    finally:
        await main_channel.close()
        await sandbox_channel.close()


async def test_entity_query_channel_closed(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """A closed channel degrades to a clean ``HomeAssistantError``."""
    bridge, main_channel, sandbox_channel = await _wire(hass)
    sandbox_entity_id = "update.synthetic"
    sandbox_channel.register("sandbox/entity_query", _entity_query_responder([], None))
    proxy = await _register(bridge, sandbox_channel, entry, "update", sandbox_entity_id)
    await main_channel.close()
    await sandbox_channel.close()

    with pytest.raises(HomeAssistantError):
        await proxy.async_release_notes()
