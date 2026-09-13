"""Viessmann ViCare DHW circulation schedule calendar."""

from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any, override

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import PyViCareNotSupportedFeatureError

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .entity import ViCareEntity
from .types import ViCareConfigEntry, ViCareDevice
from .utils import is_supported

# Short weekday keys PyViCare uses, indexed by datetime.weekday().
CIRCULATION_SCHEDULE_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Only need to look one week ahead to find the next occurrence of a
# recurring weekly schedule slot.
CIRCULATION_SCHEDULE_LOOKAHEAD = timedelta(days=7)


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareCirculationScheduleCalendar]:
    """Create ViCare DHW circulation schedule calendar entities for a device."""

    return [
        ViCareCirculationScheduleCalendar(device.serial, device.config, device.api)
        for device in device_list
        if is_supported(
            "circulation_schedule",
            lambda api: api.getDomesticHotWaterCirculationSchedule(),
            device.api,
        )
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ViCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ViCare calendar platform."""
    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            config_entry.runtime_data.devices,
        )
    )


class ViCareCirculationScheduleCalendar(ViCareEntity, CalendarEntity):
    """Representation of a ViCare DHW circulation pump schedule."""

    _attr_translation_key = "circulation_schedule"
    _circulation_schedule: dict[str, Any] | None = None

    def __init__(
        self,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
    ) -> None:
        """Initialize the circulation schedule calendar."""
        super().__init__("circulation_schedule", device_serial, device_config, device)
        self.update()

    def update(self) -> None:
        """Let HA know there has been an update from the ViCare API."""
        with (
            self.vicare_api_handler(),
            suppress(PyViCareNotSupportedFeatureError),
        ):
            self._circulation_schedule = (
                self._api.getDomesticHotWaterCirculationSchedule()
            )

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()
        events = self._get_events(now, now + CIRCULATION_SCHEDULE_LOOKAHEAD)
        return next(iter(events), None)

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return self._get_events(start_date, end_date)

    def _get_events(
        self, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the schedule slots that fall within a datetime range."""
        if not self._circulation_schedule:
            return []
        if self._circulation_schedule.get("active") is False:
            return []

        events: list[CalendarEvent] = []
        date = start_date
        while date.date() <= end_date.date():
            weekday = CIRCULATION_SCHEDULE_WEEKDAYS[date.weekday()]
            for slot in self._circulation_schedule.get(weekday, []):
                event = self._slot_to_event(date, slot)
                if event.end <= start_date or event.start >= end_date:
                    continue
                events.append(event)
            date += timedelta(days=1)
        events.sort(key=lambda event: event.start)
        return events

    def _slot_to_event(self, date: datetime, slot: dict[str, Any]) -> CalendarEvent:
        """Convert a single schedule slot on a given date into a calendar event."""
        start_hour, start_minute = (int(part) for part in slot["start"].split(":"))
        end_hour, end_minute = (int(part) for part in slot["end"].split(":"))

        day_offset = 0
        if end_hour == 24:
            end_hour = 0
            day_offset = 1

        return CalendarEvent(
            start=date.replace(
                hour=start_hour, minute=start_minute, second=0, microsecond=0
            ),
            end=date.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
            + timedelta(days=day_offset),
            summary=slot["mode"],
        )
