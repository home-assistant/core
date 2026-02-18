"""Calendar platform for the School Holidays integration."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
import re
from typing import Any

import aiohttp

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_COUNTRY, CONF_REGION

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup the School Holidays calendar."""
    country = str(entry.data.get(CONF_COUNTRY))
    region = str(entry.data.get(CONF_REGION))
    name = str(entry.data.get(CONF_NAME))

    async_add_entities(
        [SchoolHolidaysCalendarEntity(hass, name, country, region)], True
    )


class SchoolHolidaysCalendarEntity(CalendarEntity):
    """Representation of the School Holidays calendar."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:school"
    _attr_translation_key = "school_holidays"

    def __init__(
        self, hass: HomeAssistant, name: str | None, country: str, region: str
    ) -> None:
        """Initialize the calendar entity."""
        self.hass = hass
        self._attr_name = name
        self._country = country
        self._region = region.lower() if region else None
        self._events: list[dict[str, Any]] = []

    @staticmethod
    def _ensure_date(value: str | date) -> date:
        """Convert a value into a date object (without time) to ensure all-day events."""
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                # Parse as datetime, then get date
                return datetime.fromisoformat(value).date()
            except ValueError:
                # Fallback to date string
                return date.fromisoformat(value)
        raise TypeError(
            f"Value {value} must be a string or date, but got {type(value)}"
        )

    # @staticmethod
    def _create_event(
        self,
        events: list[dict[str, Any]],
        summary: str,
        start: date,
        end: date,
        description: str | None,
    ) -> None:
        """Create and append a calendar event."""
        # Remove all HTML character entities, e.g., &sup1;, &amp;
        description = (
            re.sub(r"&[a-zA-Z0-9#]+;", "", description) if description else None
        )

        start = self._ensure_date(start)
        # Add 1 day to make the end date inclusive
        end = self._ensure_date(end) + timedelta(days=1)

        events.append(
            {
                "summary": summary,
                "start": start,
                "end": end,
                "description": description,
            }
        )

    async def async_update(self) -> None:
        """Update the calendar events."""
        # Use the correct method based on the selected country
        country_methods = {
            "The Netherlands": self._get_school_holidays_nl,
        }

        country_method = country_methods.get(self._country)
        if country_method:
            _LOGGER.debug("Retrieving school holidays for country '%s'", self._country)
            self._events = await country_method()
        else:
            _LOGGER.warning(
                "No school holiday data handler for country '%s'", self._country
            )
            self._events = []

    async def _get_school_holidays_nl(self) -> list[dict[str, Any]]:
        """Get the school holidays for the selected region in The Netherlands."""
        url = "https://opendata.rijksoverheid.nl/v1/sources/rijksoverheid/infotypes/schoolholidays?output=json"
        events: list[dict[str, Any]] = []

        _LOGGER.debug("Retrieving school holidays from '%s'", url)
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response,
            ):
                if response.status != 200:
                    return []

                data = await response.json()
        except aiohttp.ClientError, TimeoutError:
            return []

        try:
            # Flatten all contents from all items
            all_contents = []
            item_descriptions = {}

            for item in data:
                contents = item.get("content", [])
                if contents:
                    all_contents.extend(contents)
                    # Map content ID (if any) to notice for later use
                    for content in contents:
                        item_descriptions[id(content)] = item.get("notice")

            # Flatten all vacations from all contents
            all_vacations = []

            for content in all_contents:
                vacations = content.get("vacations", [])
                if vacations:
                    all_vacations.extend(
                        [(vacation, content) for vacation in vacations]
                    )

            school_holidays = []

            for vacation, content in all_vacations:
                summary = vacation.get("type").strip()
                regions = vacation.get("regions", [])
                compulsory_dates = vacation.get("compulsorydates")
                use_notice = compulsory_dates is False or (
                    isinstance(compulsory_dates, str)
                    and compulsory_dates.lower() == "false"
                )

                for region_data in regions or []:
                    region = region_data.get("region").lower()
                    if region not in (self._region, "heel nederland"):
                        continue

                    description = (
                        item_descriptions.get(id(content)) if use_notice else None
                    )

                    school_holidays.append((summary, region_data, description))

            for summary, region_data, description in school_holidays:
                region = region_data.get("region")
                start = region_data.get("startdate")
                end = region_data.get("enddate")
                if not start or not end:
                    continue

                _LOGGER.debug(
                    "Found school holiday '%s' for region '%s' from %s to %s",
                    summary,
                    region,
                    start,
                    end,
                )

                self._create_event(
                    events,
                    summary,
                    start,
                    end,
                    description,
                )
        except KeyError, TypeError, ValueError:
            return []

        return events

    @property
    def event(self) -> CalendarEvent | None:
        """Get the next upcoming school holiday."""
        if not self._events:
            return None

        now = date.today()
        upcoming = [e for e in self._events if e["end"] > now]

        if upcoming:
            event = upcoming[0]

            return CalendarEvent(
                summary=event["summary"],
                start=event["start"],
                end=event["end"],
                description=event.get("description"),
            )

        return None

    async def async_get_events(
        self, _hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get the school holidays within the specified date range."""
        return [
            CalendarEvent(
                summary=event["summary"],
                start=event["start"],
                end=event["end"],
                description=event.get("description"),
            )
            for event in self._events
            if event["start"] < end_date.date() and event["end"] > start_date.date()
        ]
