"""Intents for the calendar integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util

from . import SERVICE_GET_EVENTS
from .const import DOMAIN

INTENT_CALENDAR_GET_EVENTS = "HassCalendarGetEvents"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the calendar intents."""
    intent.async_register(hass, CalendarGetEvents())


class CalendarGetEvents(intent.IntentHandler):
    """Handle CalendarGetEvents intent."""

    intent_type = INTENT_CALENDAR_GET_EVENTS
    description = (
        "Get events from a calendar. "
        "When asked when something happens, search the whole week. "
        "Results are RFC 5545 which means 'end' is exclusive."
    )
    slot_schema = {
        vol.Required("calendar"): cv.string,
        vol.Required("range"): vol.In(["today", "week"]),
    }
    platforms = {DOMAIN}

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass

        slots = self.async_validate_slots(intent_obj.slots)
        match_constraints = intent.MatchTargetsConstraints(
            name=slots["calendar"]["value"],
            domains=[DOMAIN],
        )
        match_result = intent.async_match_targets(hass, match_constraints)
        if not match_result.is_match:
            raise intent.MatchFailedError(
                result=match_result, constraints=match_constraints
            )

        entity_id = match_result.states[0].entity_id
        start, end = self._get_date_range(slots["range"]["value"])

        service_data = {
            "entity_id": entity_id,
            "start_date_time": start.isoformat(),
            "end_date_time": end.isoformat(),
        }

        service_result = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_EVENTS,
            service_data,
            blocking=True,
            return_response=True,
        )

        events = [
            event if "T" in event["start"] else {**event, "all_day": True}
            for event in cast(dict, service_result)[entity_id]["events"]
        ]

        return self._create_response(intent_obj, events)

    def _get_date_range(self, range_value: str) -> tuple[datetime, datetime]:
        """Get start and end dates based on the range."""
        now = dt_util.now()
        if range_value == "today":
            return (now, dt_util.start_of_local_day() + timedelta(days=1))
        if range_value == "week":
            return (now, dt_util.start_of_local_day() + timedelta(days=7))
        raise ValueError(f"Invalid range: {range_value}")

    def _create_response(
        self, intent_obj: intent.Intent, events: list[dict]
    ) -> intent.IntentResponse:
        """Create response with event details."""
        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.QUERY_ANSWER

        statuses = [
            {
                "start": event["start"],
                "end": event["end"],
                "all_day": "T" not in event["start"],
                "summary": event["summary"],
                "description": event["description"],
                "location": event.get("location", ""),
                "recurring": event.get("recurring"),
            }
            for event in events
        ]

        response.async_set_speech_slots({"events": statuses})
        return response
