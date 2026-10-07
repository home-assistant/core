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


def _as_datetime(value: date | datetime) -> datetime:
    """Normalise a CalendarEvent start/end (date or datetime) to a datetime."""
    if isinstance(value, datetime):
        return value
    return dt_util.start_of_local_day(value)


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
        # last day (or a timestamp at the frame's midnight) — normalise to date
        # and always advance by one day so the final day is kept.
        end_date = end.date() if isinstance(end, datetime) else end
        end_date = end_date + timedelta(days=1)
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
        self._window_min: date | None = None
        self._window_max: date | None = None

    @override
    async def _async_update_data(self) -> SkylightData:
        today = dt_util.now().date()
        self._window_min = today - timedelta(days=EVENTS_PAST_DAYS)
        self._window_max = today + timedelta(days=EVENTS_FUTURE_DAYS)
        return SkylightData(
            events=await self._async_fetch_events(
                self._window_min.isoformat(), self._window_max.isoformat()
            )
        )

    async def _async_fetch_events(
        self, date_min: str, date_max: str
    ) -> list[CalendarEvent]:
        """Fetch raw events for an inclusive date range and parse them."""
        frame_id = self.config_entry.data[CONF_FRAME_ID]
        try:
            raw = await self.api.get_calendar_events(
                frame_id, date_min=date_min, date_max=date_max
            )
        except SkylightAuthError as err:
            raise ConfigEntryAuthFailed from err
        except SkylightAPIError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(err)},
            ) from err

        return [
            event
            for item in raw.get("data", [])
            if (event := _event_from_raw(item)) is not None
        ]

    async def async_events_between(
        self, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return events between two datetimes, fetching beyond the poll window."""
        window_events = [
            event
            for event in self.data.events
            if _as_datetime(event.start) < end_date
            and _as_datetime(event.end) > start_date
        ]
        if self._window_min is None or self._window_max is None:
            return window_events
        if (
            start_date.date() >= self._window_min
            and end_date.date() <= self._window_max
        ):
            return window_events

        # The requested range extends past the rolling poll window: fetch it
        # live so calendar views outside the window are still complete. If the
        # fetch fails, degrade to the cached window instead of failing the
        # calendar service call.
        try:
            extra = await self._async_fetch_events(
                start_date.date().isoformat(), end_date.date().isoformat()
            )
        except ConfigEntryAuthFailed, UpdateFailed:
            return window_events

        seen = {event.uid for event in window_events if event.uid is not None}
        merged = list(window_events)
        for event in extra:
            # Only merge events that actually overlap the requested range; the
            # API may return adjacent events outside the requested bounds.
            if not (
                _as_datetime(event.start) < end_date
                and _as_datetime(event.end) > start_date
            ):
                continue
            if event.uid is None:
                merged.append(event)
                continue
            if event.uid not in seen:
                seen.add(event.uid)
                merged.append(event)
        return merged
