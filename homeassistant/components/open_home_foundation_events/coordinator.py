"""Coordinator for the Open Home Foundation Events integration."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, override

from aiohttp import ClientError

from homeassistant.components.calendar import CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_URL, DOMAIN, LOGGER

type OHFEventsConfigEntry = ConfigEntry[OHFEventsCoordinator]

SCAN_INTERVAL = timedelta(minutes=30)
DEFAULT_EVENT_DURATION = timedelta(hours=1)


@dataclass(frozen=True, kw_only=True)
class OHFEvent:
    """An event with the coordinates of its venue."""

    event: CalendarEvent
    latitude: float
    longitude: float


def _parse_moment(value: str) -> datetime | date:
    """Parse a UTC date-time or an all-day date."""
    if "T" in value:
        return datetime.fromisoformat(value)
    return date.fromisoformat(value)


def _parse_event(raw: dict[str, Any]) -> OHFEvent | None:
    """Parse an API event, skipping events that cannot be placed on a map."""
    if (
        raw.get("status") == "cancelled"
        or raw.get("latitude") is None
        or raw.get("longitude") is None
    ):
        return None

    start = _parse_moment(raw["start"])
    if raw.get("end") is not None:
        end = _parse_moment(raw["end"])
    elif isinstance(start, datetime):
        end = start + DEFAULT_EVENT_DURATION
    else:
        end = start + timedelta(days=1)

    return OHFEvent(
        event=CalendarEvent(
            start=start,
            end=end,
            summary=raw["summary"],
            description=raw.get("description"),
            location=raw.get("location"),
            uid=raw["id"],
        ),
        latitude=raw["latitude"],
        longitude=raw["longitude"],
    )


class OHFEventsCoordinator(DataUpdateCoordinator[list[OHFEvent]]):
    """Fetch all events of the Open Home Foundation in a single request."""

    config_entry: OHFEventsConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: OHFEventsConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._session = async_get_clientsession(hass)

    @override
    async def _async_update_data(self) -> list[OHFEvent]:
        """Fetch the events of every tracked calendar."""
        try:
            response = await self._session.get(API_URL)
            response.raise_for_status()
            calendars: list[dict[str, Any]] = await response.json()
        except (ClientError, TimeoutError, ValueError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

        events: dict[str, OHFEvent] = {}
        try:
            for calendar in calendars:
                for raw in calendar["events"]:
                    if (parsed := _parse_event(raw)) is not None:
                        events.setdefault(raw["id"], parsed)
        except (KeyError, TypeError, ValueError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_response",
            ) from err
        return list(events.values())
