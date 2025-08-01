"""Creates a calendar entity for the mower."""

from datetime import datetime
import logging
from typing import TYPE_CHECKING

from aioautomower.model import make_name_string

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import AutomowerConfigEntry
from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerBaseEntity

_LOGGER = logging.getLogger(__name__)
# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lawn mower platform."""
    coordinator = entry.runtime_data

    def _async_add_new_devices(mower_ids: set[str]) -> None:
        async_add_entities(
            AutomowerCalendarEntity(mower_id, coordinator) for mower_id in mower_ids
        )

    coordinator.new_devices_callbacks.append(_async_add_new_devices)
    _async_add_new_devices(set(coordinator.data))


class AutomowerCalendarEntity(AutomowerBaseEntity, CalendarEntity):
    """Representation of the Automower Calendar element."""

    _attr_name: str | None = None

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Set up AutomowerCalendarEntity."""
        super().__init__(mower_id, coordinator)
        self._attr_unique_id = mower_id
        self._event: CalendarEvent | None = None

    @property
    def device_name(self) -> str:
        """Return the prefix for the event summary."""
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, self.mower_id)}
        )
        if TYPE_CHECKING:
            assert device_entry is not None
            assert device_entry.name is not None

        return device_entry.name_by_user or device_entry.name

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event."""
        if not self.available:
            return None
        schedule = self.mower_attributes.calendar
        cursor = schedule.timeline.active_after(dt_util.now())
        program_event = next(cursor, None)
        if not program_event:
            return None
        work_area_name = None
        if self.mower_attributes.work_area_dict and program_event.work_area_id:
            work_area_name = self.mower_attributes.work_area_dict[
                program_event.work_area_id
            ]
        return CalendarEvent(
            summary=f"{self.device_name} {make_name_string(work_area_name, program_event.schedule_no)}",
            start=program_event.start,
            end=program_event.end,
            rrule=program_event.rrule_str,
        )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range.

        This is only called when opening the calendar in the UI.
        """
        if not self.available:
            return []
        schedule = self.mower_attributes.calendar
        cursor = schedule.timeline.overlapping(
            start_date,
            end_date,
        )
        calendar_events = []
        for program_event in cursor:
            work_area_name = None
            if self.mower_attributes.work_area_dict and program_event.work_area_id:
                work_area_name = self.mower_attributes.work_area_dict[
                    program_event.work_area_id
                ]
            calendar_events.append(
                CalendarEvent(
                    summary=f"{self.device_name} {make_name_string(work_area_name, program_event.schedule_no)}",
                    start=program_event.start.replace(tzinfo=start_date.tzinfo),
                    end=program_event.end.replace(tzinfo=start_date.tzinfo),
                    rrule=program_event.rrule_str,
                )
            )
        return calendar_events
