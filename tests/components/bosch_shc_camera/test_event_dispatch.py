"""Tests for event_dispatch.py's new-event bus dispatch.

The three custom bus events fired here are the ONLY notification mechanism
this snapshot-only integration provides (no binary_sensor/other platform
exists in this reduced scope) — pinned as supported functionality, not
untested internals (Copilot review round 7).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from homeassistant.components.bosch_shc_camera.event_dispatch import _dispatch_new_event

CAM_ID = "AABBCCDD-1122-3344-5566-778899001122"


def _make_coord(**overrides: object) -> SimpleNamespace:
    coord = SimpleNamespace(
        alert_sent_ids=overrides.pop("alert_sent_ids", {}),
        last_event_ids=overrides.pop("last_event_ids", {}),
        camera_entities=overrides.pop("camera_entities", {}),
        hass=MagicMock(),
        spawn_tracked=MagicMock(),
    )
    for key, value in overrides.items():
        setattr(coord, key, value)
    return coord


def test_movement_event_fires_motion_bus_event() -> None:
    """A MOVEMENT event fires `bosch_shc_camera_motion` with the documented payload."""
    coord = _make_coord()
    events = [
        {
            "id": "ev2",
            "eventType": "MOVEMENT",
            "timestamp": "2026-07-27T00:00:00Z",
            "imageUrl": "https://events.cbs.boschsecurity.com/x.jpg",
        }
    ]

    _dispatch_new_event(coord, CAM_ID, {"title": "Front Door"}, events, "ev2")

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


def test_audio_alarm_event_fires_audio_alarm_bus_event() -> None:
    """An AUDIO_ALARM event fires `bosch_shc_camera_audio_alarm`."""
    coord = _make_coord()
    events = [{"id": "ev2", "eventType": "AUDIO_ALARM"}]

    _dispatch_new_event(coord, CAM_ID, {"title": "Front Door"}, events, "ev2")

    assert coord.hass.bus.async_fire.call_args[0][0] == "bosch_shc_camera_audio_alarm"


def test_person_event_fires_person_bus_event() -> None:
    """A PERSON event fires `bosch_shc_camera_person`."""
    coord = _make_coord()
    events = [{"id": "ev2", "eventType": "PERSON"}]

    _dispatch_new_event(coord, CAM_ID, {"title": "Front Door"}, events, "ev2")

    assert coord.hass.bus.async_fire.call_args[0][0] == "bosch_shc_camera_person"


def test_movement_with_person_tag_upgrades_to_person_event() -> None:
    """Gen2 DualRadar fires MOVEMENT+eventTags=[PERSON] — upgrade to the more specific type."""
    coord = _make_coord()
    events = [{"id": "ev2", "eventType": "MOVEMENT", "eventTags": ["PERSON"]}]

    _dispatch_new_event(coord, CAM_ID, {"title": "Front Door"}, events, "ev2")

    assert coord.hass.bus.async_fire.call_args[0][0] == "bosch_shc_camera_person"


def test_unknown_event_type_fires_no_bus_event() -> None:
    """An unrecognized eventType must not fire any bus event."""
    coord = _make_coord()
    events = [{"id": "ev2", "eventType": "SOMETHING_ELSE"}]

    _dispatch_new_event(coord, CAM_ID, {"title": "Front Door"}, events, "ev2")

    coord.hass.bus.async_fire.assert_not_called()


def test_dedup_within_60s_window_skips_bus_fire() -> None:
    """The same event id re-dispatched within 60s of itself must not re-fire."""
    coord = _make_coord(alert_sent_ids={"ev2": 1000.0})
    events = [{"id": "ev2", "eventType": "MOVEMENT"}]

    with patch(
        "homeassistant.components.bosch_shc_camera.event_dispatch.time.monotonic",
        return_value=1010.0,
    ):
        _dispatch_new_event(coord, CAM_ID, {"title": "Front Door"}, events, "ev2")

    coord.hass.bus.async_fire.assert_not_called()
    assert coord.last_event_ids[CAM_ID] == "ev2"


def test_triggers_camera_image_refresh_when_entity_registered() -> None:
    """A new event schedules a background image refresh via spawn_tracked."""
    coord = _make_coord()
    cam_entity = MagicMock()
    coord.camera_entities[CAM_ID] = cam_entity
    events = [{"id": "ev2", "eventType": "MOVEMENT"}]

    _dispatch_new_event(coord, CAM_ID, {"title": "Front Door"}, events, "ev2")

    coord.spawn_tracked.assert_called_once()


def test_no_camera_entity_registered_skips_refresh_without_error() -> None:
    """No registered camera entity for cam_id must not raise or refresh."""
    coord = _make_coord()
    events = [{"id": "ev2", "eventType": "MOVEMENT"}]

    _dispatch_new_event(coord, CAM_ID, {"title": "Front Door"}, events, "ev2")

    coord.spawn_tracked.assert_not_called()
