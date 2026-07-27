"""Tests for event_dispatch.py's per-camera data-build + new-event dispatch.

The three custom bus events fired here are the ONLY notification mechanism
this snapshot-only integration provides (no binary_sensor/other platform
exists in this reduced scope) — pinned as supported functionality, not
untested internals (Copilot review round 7).

Exercised through `build_data_and_dispatch` (the function the coordinator's
real polling tick actually calls) rather than the private `_dispatch_new_event`
directly — a test that only calls the private helper can keep passing even if
the real polling/build wiring stops reaching it (Copilot review round 9).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.bosch_shc_camera.event_dispatch import (
    build_data_and_dispatch,
)

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"
NOW = 1000.0


def _make_coord(**overrides: object) -> SimpleNamespace:
    coord = SimpleNamespace(
        cached_status=overrides.pop("cached_status", {}),
        cached_events=overrides.pop("cached_events", {}),
        last_event_ids=overrides.pop("last_event_ids", {}),
        alert_sent_ids=overrides.pop("alert_sent_ids", {}),
        camera_entities=overrides.pop("camera_entities", {}),
        hass=MagicMock(),
        spawn_tracked=MagicMock(),
    )
    for key, value in overrides.items():
        setattr(coord, key, value)
    return coord


def _cam_by_id(cam_id: str = CAM_ID, title: str = "Front Door") -> dict:
    return {cam_id: {"id": cam_id, "title": title}}


@pytest.mark.asyncio
async def test_movement_event_fires_motion_bus_event() -> None:
    """A MOVEMENT event fires `bosch_shc_camera_motion` with the documented payload."""
    coord = _make_coord(
        cached_status={CAM_ID: "ONLINE"},
        cached_events={
            CAM_ID: [
                {
                    "id": "ev2",
                    "eventType": "MOVEMENT",
                    "timestamp": "2026-07-27T00:00:00Z",
                    "imageUrl": "https://events.cbs.boschsecurity.com/x.jpg",
                }
            ]
        },
        last_event_ids={CAM_ID: "ev1"},
    )

    await build_data_and_dispatch(coord, [CAM_ID], _cam_by_id(), NOW, True)

    coord.hass.bus.async_fire.assert_called_once()
    event_name, payload = coord.hass.bus.async_fire.call_args[0]
    assert event_name == "bosch_shc_camera_motion"
    assert payload == {
        "camera_id": CAM_ID,
        "camera_name": "Front Door",
        "timestamp": "2026-07-27T00:00:00Z",
        "image_url": "https://events.cbs.boschsecurity.com/x.jpg",
        "event_id": "ev2",
    }
    assert coord.last_event_ids[CAM_ID] == "ev2"


@pytest.mark.asyncio
async def test_audio_alarm_event_fires_audio_alarm_bus_event() -> None:
    """An AUDIO_ALARM event fires `bosch_shc_camera_audio_alarm`."""
    coord = _make_coord(
        cached_events={CAM_ID: [{"id": "ev2", "eventType": "AUDIO_ALARM"}]},
        last_event_ids={CAM_ID: "ev1"},
    )

    await build_data_and_dispatch(coord, [CAM_ID], _cam_by_id(), NOW, True)

    assert coord.hass.bus.async_fire.call_args[0][0] == "bosch_shc_camera_audio_alarm"


@pytest.mark.asyncio
async def test_person_event_fires_person_bus_event() -> None:
    """A PERSON event fires `bosch_shc_camera_person`."""
    coord = _make_coord(
        cached_events={CAM_ID: [{"id": "ev2", "eventType": "PERSON"}]},
        last_event_ids={CAM_ID: "ev1"},
    )

    await build_data_and_dispatch(coord, [CAM_ID], _cam_by_id(), NOW, True)

    assert coord.hass.bus.async_fire.call_args[0][0] == "bosch_shc_camera_person"


@pytest.mark.asyncio
async def test_movement_with_person_tag_upgrades_to_person_event() -> None:
    """Gen2 DualRadar fires MOVEMENT+eventTags=[PERSON] — upgrade to the more specific type."""
    coord = _make_coord(
        cached_events={
            CAM_ID: [{"id": "ev2", "eventType": "MOVEMENT", "eventTags": ["PERSON"]}]
        },
        last_event_ids={CAM_ID: "ev1"},
    )

    await build_data_and_dispatch(coord, [CAM_ID], _cam_by_id(), NOW, True)

    assert coord.hass.bus.async_fire.call_args[0][0] == "bosch_shc_camera_person"


@pytest.mark.asyncio
async def test_unknown_event_type_fires_no_bus_event() -> None:
    """An unrecognized eventType must not fire any bus event."""
    coord = _make_coord(
        cached_events={CAM_ID: [{"id": "ev2", "eventType": "SOMETHING_ELSE"}]},
        last_event_ids={CAM_ID: "ev1"},
    )

    await build_data_and_dispatch(coord, [CAM_ID], _cam_by_id(), NOW, True)

    coord.hass.bus.async_fire.assert_not_called()


@pytest.mark.asyncio
async def test_dedup_within_60s_window_skips_bus_fire() -> None:
    """The same event id re-dispatched within 60s of itself must not re-fire."""
    coord = _make_coord(
        cached_events={CAM_ID: [{"id": "ev2", "eventType": "MOVEMENT"}]},
        last_event_ids={CAM_ID: "ev1"},
        alert_sent_ids={"ev2": 1000.0},
    )

    with patch(
        "homeassistant.components.bosch_shc_camera.event_dispatch.time.monotonic",
        return_value=1010.0,
    ):
        await build_data_and_dispatch(coord, [CAM_ID], _cam_by_id(), NOW, True)

    coord.hass.bus.async_fire.assert_not_called()
    assert coord.last_event_ids[CAM_ID] == "ev2"


@pytest.mark.asyncio
async def test_triggers_camera_image_refresh_when_entity_registered() -> None:
    """A new event schedules a background image refresh via spawn_tracked."""
    coord = _make_coord(
        cached_events={CAM_ID: [{"id": "ev2", "eventType": "MOVEMENT"}]},
        last_event_ids={CAM_ID: "ev1"},
    )
    coord.camera_entities[CAM_ID] = MagicMock()

    await build_data_and_dispatch(coord, [CAM_ID], _cam_by_id(), NOW, True)

    coord.spawn_tracked.assert_called_once()


@pytest.mark.asyncio
async def test_no_camera_entity_registered_skips_refresh_without_error() -> None:
    """No registered camera entity for cam_id must not raise or refresh."""
    coord = _make_coord(
        cached_events={CAM_ID: [{"id": "ev2", "eventType": "MOVEMENT"}]},
        last_event_ids={CAM_ID: "ev1"},
    )

    await build_data_and_dispatch(coord, [CAM_ID], _cam_by_id(), NOW, True)

    coord.spawn_tracked.assert_not_called()


@pytest.mark.asyncio
async def test_no_prior_last_event_id_bootstraps_without_firing() -> None:
    """First-ever poll (no FCM, no prior last_event_ids entry) must seed the id.

    Seeds it so the NEXT tick can detect a change, without firing a bus
    event for an event that may have happened before this integration was
    ever set up.
    """
    coord = _make_coord(
        cached_events={CAM_ID: [{"id": "ev1", "eventType": "MOVEMENT"}]},
    )

    await build_data_and_dispatch(coord, [CAM_ID], _cam_by_id(), NOW, True)

    coord.hass.bus.async_fire.assert_not_called()
    assert coord.last_event_ids[CAM_ID] == "ev1"


@pytest.mark.asyncio
async def test_do_events_false_skips_dispatch_entirely() -> None:
    """`do_events=False` (slow-tier tick that skipped the events fetch) must skip processing.

    Must not process cached_events at all — no bus fire, no
    last_event_ids write.
    """
    coord = _make_coord(
        cached_events={CAM_ID: [{"id": "ev2", "eventType": "MOVEMENT"}]},
        last_event_ids={CAM_ID: "ev1"},
    )

    await build_data_and_dispatch(coord, [CAM_ID], _cam_by_id(), NOW, False)

    coord.hass.bus.async_fire.assert_not_called()
    assert coord.last_event_ids[CAM_ID] == "ev1"
