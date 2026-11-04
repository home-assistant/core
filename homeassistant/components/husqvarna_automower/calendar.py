"""Creates a calendar entity for the mower."""

from datetime import datetime
import logging
from typing import TYPE_CHECKING, override

from aioautomower.model import make_name_string

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import AutomowerConfigEntry, AutomowerDataUpdateCoordinator
from .entity import AutomowerBaseEntity, WorkAreaAvailableEntity

_LOGGER = logging.getLogger(__name__)
# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0
WORK_AREA_DEPRECATED_DESCRIPTION = (
    "This calendar event is deprecated. "
    "Please use the dedicated Work Area calendar instead."
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number platform."""
    coordinator = entry.runtime_data
    entities: list[CalendarEntity] = []
    for mower_id in coordinator.data:
        if coordinator.data[mower_id].capabilities.work_areas:
            _work_areas = coordinator.data[mower_id].work_areas
            if _work_areas is not None:
                entities.extend(
                    WorkAreaCalendarEntity(mower_id, coordinator, work_area_id)
                    for work_area_id in _work_areas
                )
        entities.append(AutomowerCalendarEntity(mower_id, coordinator))
    async_add_entities(entities)

    def _async_add_new_work_areas(mower_id: str, work_area_ids: set[int]) -> None:
        async_add_entities(
            WorkAreaCalendarEntity(mower_id, coordinator, work_area_id)
            for work_area_id in work_area_ids
        )

    def _async_add_new_devices(mower_ids: set[str]) -> None:
        async_add_entities(
            AutomowerCalendarEntity(mower_id, coordinator) for mower_id in mower_ids
        )
        for mower_id in mower_ids:
            mower_data = coordinator.data[mower_id]
            if mower_data.capabilities.work_areas and mower_data.work_areas is not None:
                work_area_ids = set(mower_data.work_areas.keys())
                _async_add_new_work_areas(mower_id, work_area_ids)

    coordinator.new_areas_callbacks.append(_async_add_new_work_areas)
    coordinator.new_devices_callbacks.append(_async_add_new_devices)


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
        device_entry = self.device_entry
        if TYPE_CHECKING:
            assert device_entry is not None
            assert device_entry.name is not None

        return device_entry.name_by_user or device_entry.name

    @property
    @override
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
        if (work_area_dict := self.mower_attributes.work_area_dict) and (
            work_area_id := program_event.work_area_id
        ) is not None:
            work_area_name = work_area_dict.get(work_area_id)
        name_str = make_name_string(work_area_name, program_event.schedule_no)
        return CalendarEvent(
            summary=f"{self.device_name} {name_str}",
            start=program_event.start,
            end=program_event.end,
            rrule=program_event.rrule_str,
            description=(
                WORK_AREA_DEPRECATED_DESCRIPTION
                if program_event.work_area_id is not None
                else None
            ),
        )

    @override
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
            if (work_area_dict := self.mower_attributes.work_area_dict) and (
                work_area_id := program_event.work_area_id
            ) is not None:
                work_area_name = work_area_dict.get(work_area_id)
            name_str = make_name_string(work_area_name, program_event.schedule_no)
            calendar_events.append(
                CalendarEvent(
                    start=program_event.start.replace(tzinfo=start_date.tzinfo),
                    end=program_event.end.replace(tzinfo=start_date.tzinfo),
                    summary=f"{self.device_name} {name_str}",
                    rrule=program_event.rrule_str,
                    description=(
                        WORK_AREA_DEPRECATED_DESCRIPTION
                        if program_event.work_area_id is not None
                        else None
                    ),
                )
            )
        return calendar_events


class WorkAreaCalendarEntity(WorkAreaAvailableEntity, CalendarEntity):
    """Representation of the Automower Calendar element."""

    _attr_name: str | None = None

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        work_area_id: int,
    ) -> None:
        """Set up WorkAreaCalendarEntity."""
        super().__init__(mower_id, coordinator, work_area_id)
        self._attr_unique_id = f"{mower_id}_{work_area_id}"
        self._event: CalendarEvent | None = None
        self.work_area_id = work_area_id

    @property
    def device_name(self) -> str:
        """Return the prefix for the event summary."""
        device_entry = self.device_entry
        if TYPE_CHECKING:
            assert device_entry is not None
            assert device_entry.name is not None

        return device_entry.name_by_user or device_entry.name

    @property
    @override
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
        if (work_area_dict := self.mower_attributes.work_area_dict) and (
            work_area_id := program_event.work_area_id
        ) is not None:
            work_area_name = work_area_dict.get(work_area_id)
        name_str = make_name_string(work_area_name, program_event.schedule_no)
        return CalendarEvent(
            summary=f"{self.device_name} {name_str}",
            start=program_event.start,
            end=program_event.end,
            rrule=program_event.rrule_str,
        )

    @override
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
            if program_event.work_area_id != self.work_area_id:
                continue

            work_area_name = None
            if work_area_dict := self.mower_attributes.work_area_dict:
                work_area_name = work_area_dict.get(self.work_area_id)

            name_str = make_name_string(work_area_name, program_event.schedule_no)
            calendar_events.append(
                CalendarEvent(
                    summary=name_str,
                    start=program_event.start.replace(tzinfo=start_date.tzinfo),
                    end=program_event.end.replace(tzinfo=start_date.tzinfo),
                    rrule=program_event.rrule_str,
                )
            )
        return calendar_events
