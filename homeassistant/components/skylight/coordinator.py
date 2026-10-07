"""DataUpdateCoordinator for the Skylight integration."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Any, override

from skylight_api import SkylightAPI, SkylightAPIError, SkylightAuthError

from homeassistant.components.calendar import CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FRAME_ID,
    DOMAIN,
    EVENTS_FUTURE_DAYS,
    EVENTS_PAST_DAYS,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type SkylightConfigEntry = ConfigEntry[SkylightDataUpdateCoordinator]


@dataclass
class SkylightData:
    """Skylight data type."""

    events: list[CalendarEvent]


def _parse_wire_datetime(value: str) -> date | datetime:
    """Parse a Skylight wire datetime: a bare date is an all-day marker."""
    if len(value) == 10:
        return date.fromisoformat(value)
    if (parsed := dt_util.parse_datetime(value)) is not None:
        return parsed
    raise ValueError(f"Unparsable Skylight datetime: {value}")


def _event_from_raw(raw: dict[str, Any]) -> CalendarEvent | None:
    """Convert one JSON:API calendar_event record to a Home Assistant event."""
    attrs = raw.get("attributes", {}) or {}
    starts = attrs.get("starts_at")
    ends = attrs.get("ends_at")
    if not starts or not ends:
        return None
    try:
        start = _parse_wire_datetime(starts)
        end = _parse_wire_datetime(ends)
    except ValueError:
        _LOGGER.debug("Skipping event %s with unparsable dates", raw.get("id"))
        return None

    if not isinstance(start, datetime):
        # All-day: HA wants an exclusive end date. Skylight sends the inclusive
        # last day (or a timestamp at the frame's midnight) — normalise to date.
        end_date = end.date() if isinstance(end, datetime) else end
        if end_date <= start:
            end_date = start + timedelta(days=1)
        end = end_date

    return CalendarEvent(
        start=start,
        end=end,
        summary=attrs.get("summary") or "Skylight Event",
        description=attrs.get("description") or None,
        location=attrs.get("location") or None,
        uid=str(raw["id"]) if raw.get("id") is not None else None,
    )


class SkylightDataUpdateCoordinator(DataUpdateCoordinator[SkylightData]):
    """A Skylight Data Update Coordinator."""

    config_entry: SkylightConfigEntry

    def __init__(
        self, hass: HomeAssistant, api: SkylightAPI, entry: SkylightConfigEntry
    ) -> None:
        """Initialize the Skylight data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api

    @override
    async def _async_update_data(self) -> SkylightData:
        frame_id = self.config_entry.data[CONF_FRAME_ID]
        today = dt_util.now().date()
        date_min = (today - timedelta(days=EVENTS_PAST_DAYS)).isoformat()
        date_max = (today + timedelta(days=EVENTS_FUTURE_DAYS)).isoformat()
        try:
            raw = await self.api.get_calendar_events(
                frame_id, date_min=date_min, date_max=date_max
            )
        except SkylightAuthError as err:
            raise ConfigEntryAuthFailed from err
        except SkylightAPIError as err:
            raise UpdateFailed from err

        events = [
            event
            for item in raw.get("data", [])
            if (event := _event_from_raw(item)) is not None
        ]
        return SkylightData(events=events)
