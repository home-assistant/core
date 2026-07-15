"""Describe Bosch SHC Camera events in the HA Logbook.

HA auto-discovers this module via the ``logbook`` platform and calls
``async_describe_events`` once at startup so the three event types fired by
this integration appear with friendly messages instead of raw JSON dumps.

Events fired by this integration
---------------------------------
bosch_shc_camera_motion      (fcm.py:508, __init__.py:1729) — MOVEMENT
bosch_shc_camera_audio_alarm (fcm.py:510, __init__.py:1733) — AUDIO_ALARM
bosch_shc_camera_person      (fcm.py:512, __init__.py:1737) — PERSON

All three share the same payload schema::

    {
        "camera_id":   str,   # Bosch device UUID
        "camera_name": str,   # human-readable title from the Bosch app
        "timestamp":   str,   # ISO-8601 event timestamp
        "image_url":   str,   # thumbnail URL (may be empty)
        "event_id":    str,   # Bosch event ID used for mark-read
        "source":      str,   # "fcm_push" or absent (REST poll)
    }
"""

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.core import Event, HomeAssistant, callback

from .const import DOMAIN

# Internal event-type strings — must match what fcm.py / __init__.py fire.
EVENT_MOTION = "bosch_shc_camera_motion"
EVENT_AUDIO_ALARM = "bosch_shc_camera_audio_alarm"
EVENT_PERSON = "bosch_shc_camera_person"


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[
        [str, str, Callable[[Event[dict[str, Any]]], dict[str, str]]], None
    ],
) -> None:
    """Register Bosch SHC Camera logbook event descriptions."""

    @callback
    def _describe_motion(event: Event[dict[str, Any]]) -> dict[str, str]:
        """Return a friendly Logbook entry for a motion-detection event."""
        camera_name: str = event.data.get("camera_name") or "unknown camera"
        return {
            LOGBOOK_ENTRY_NAME: f"Bosch {camera_name}",
            LOGBOOK_ENTRY_MESSAGE: "detected motion",
        }

    @callback
    def _describe_audio_alarm(event: Event[dict[str, Any]]) -> dict[str, str]:
        """Return a friendly Logbook entry for an audio-alarm event."""
        camera_name: str = event.data.get("camera_name") or "unknown camera"
        return {
            LOGBOOK_ENTRY_NAME: f"Bosch {camera_name}",
            LOGBOOK_ENTRY_MESSAGE: "detected an audio alarm",
        }

    @callback
    def _describe_person(event: Event[dict[str, Any]]) -> dict[str, str]:
        """Return a friendly Logbook entry for a person-detection event."""
        camera_name: str = event.data.get("camera_name") or "unknown camera"
        return {
            LOGBOOK_ENTRY_NAME: f"Bosch {camera_name}",
            LOGBOOK_ENTRY_MESSAGE: "detected a person",
        }

    async_describe_event(DOMAIN, EVENT_MOTION, _describe_motion)
    async_describe_event(DOMAIN, EVENT_AUDIO_ALARM, _describe_audio_alarm)
    async_describe_event(DOMAIN, EVENT_PERSON, _describe_person)
