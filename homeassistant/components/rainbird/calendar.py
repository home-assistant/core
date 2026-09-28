"""Rain Bird irrigation calendar."""

from datetime import datetime
import logging
from typing import override

from pyrainbird.data import Schedule, ZoneDuration
from pyrainbird.timeline import ProgramEvent

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import RainbirdScheduleUpdateCoordinator
from .types import RainbirdConfigEntry

_LOGGER = logging.getLogger(__name__)


def _calendar_event(schedule: Schedule, program_event: ProgramEvent) -> CalendarEvent:
    """Convert a program event to a calendar event listing the zone run times."""
    durations: list[ZoneDuration] = next(
        (
            program.durations
            for program in schedule.programs
            if program.program == program_event.program_id.program
        ),
        [],
    )
    return CalendarEvent(
        summary=program_event.program_id.name,
        start=dt_util.as_local(program_event.start),
        end=dt_util.as_local(program_event.end),
        description="\n".join(
            f"{zone.name}: {int(zone.duration.total_seconds() // 60)} min"
            for zone in durations
        ),
        rrule=program_event.rrule_str,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RainbirdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird irrigation calendar."""
    data = config_entry.runtime_data
    if not data.model_info.model_info.max_programs:
        return

    async_add_entities(
        [
            RainBirdCalendarEntity(
                data.schedule_coordinator,
                data.coordinator.unique_id,
                data.coordinator.device_info,
                data.coordinator.device_name,
            )
        ]
    )


class RainBirdCalendarEntity(
    CoordinatorEntity[RainbirdScheduleUpdateCoordinator], CalendarEntity
):
    """A calendar event entity."""

    _attr_has_entity_name = True
    _attr_name: str | None = None
    _attr_translation_key = "calendar"

    def __init__(
        self,
        coordinator: RainbirdScheduleUpdateCoordinator,
        unique_id: str | None,
        device_info: DeviceInfo | None,
        device_name: str,
    ) -> None:
        """Create the Calendar event device."""
        super().__init__(coordinator)
        self._event: CalendarEvent | None = None
        if unique_id is not None:
            self._attr_unique_id = unique_id
            self._attr_device_info = device_info
        else:
            self._attr_name = device_name

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        schedule = self.coordinator.data
        if not schedule:
            return None
        cursor = schedule.timeline_tz(dt_util.get_default_time_zone()).active_after(
            dt_util.now()
        )
        program_event = next(cursor, None)
        if not program_event:
            return None
        return _calendar_event(schedule, program_event)

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        schedule = self.coordinator.data
        if not schedule:
            raise HomeAssistantError(
                "Unable to get events: No data from controller yet"
            )
        cursor = schedule.timeline_tz(start_date.tzinfo).overlapping(
            start_date,
            end_date,
        )
        return [_calendar_event(schedule, program_event) for program_event in cursor]

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # We do not ask for an update with async_add_entities()
        # because it will update disabled entities. This is started as a
        # task to let it sync in the background without blocking startup
        self.coordinator.config_entry.async_create_background_task(
            self.hass,
            self.coordinator.async_request_refresh(),
            "rainbird.calendar-refresh",
        )
