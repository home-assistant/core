"""Calendar platform for the Birthday integration."""

from datetime import date, datetime, timedelta
from typing import override

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_DAY, CONF_MONTH, CONF_PERSON, CONF_YEAR


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the birthday calendar."""
    async_add_entities([BirthdayCalendar(entry)])


def _ordinal(number: int) -> str:
    """Return a number with its English ordinal suffix (1st, 2nd, 3rd, 4th...)."""
    suffixes = {
        1: "st",
        2: "nd",  # codespell:ignore nd
        3: "rd",
    }
    if 11 <= number % 100 <= 13:
        suffix = "th"
    else:
        suffix = suffixes.get(number % 10, "th")
    return f"{number}{suffix}"


class BirthdayCalendar(CalendarEntity):
    """Calendar with all the birthdays."""

    _attr_has_entity_name = True
    _attr_translation_key = "birthdays"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the calendar."""
        self._entry = entry
        self._attr_unique_id = entry.entry_id

    @override
    async def async_added_to_hass(self) -> None:
        """Refresh the calendar when birthdays are added, edited or removed."""
        await super().async_added_to_hass()
        self._entry.async_on_unload(
            self._entry.add_update_listener(self._async_entry_updated)
        )

    async def _async_entry_updated(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Write the state and notify the event subscribers."""
        self.async_write_ha_state()

    def _events(self, start: date, end: date) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        for subentry in self._entry.subentries.values():
            data = subentry.data
            name = data[CONF_PERSON]
            birth_year = data.get(CONF_YEAR)
            for year in range(start.year, end.year + 1):
                try:
                    day = date(year, data[CONF_MONTH], data[CONF_DAY])
                except ValueError:
                    day = date(year, 3, 1)
                if not start <= day <= end:
                    continue

                if birth_year:
                    age = year - birth_year
                    if age < 1:
                        continue
                    summary = f"🎂 {name}'s {_ordinal(age)} birthday"
                    description = f"{name} turns {age}."
                else:
                    summary = f"🎂 {name}'s birthday"
                    description = None

                events.append(
                    CalendarEvent(
                        start=day,
                        end=day + timedelta(days=1),
                        summary=summary,
                        description=description,
                    )
                )
        return sorted(events, key=lambda event: event.start)

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the next birthday."""
        today = dt_util.now().date()
        events = self._events(today, today + timedelta(days=366))
        return events[0] if events else None

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return birthdays in the requested range."""
        start_day = start_date.date()
        if start_day > date.min:
            start_day -= timedelta(days=1)
        return [
            event
            for event in self._events(
                start_day, (end_date - timedelta(microseconds=1)).date()
            )
            if event.end_datetime_local >= start_date
            and event.start_datetime_local < end_date
        ]
