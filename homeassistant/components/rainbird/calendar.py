"""Rain Bird irrigation calendar."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import RainbirdScheduleUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Polling the calendar requires a number of RPC calls to fetch the data and
# we don't expect the calendar to change often, so use a long schedule.
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird irrigation calendar."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id].coordinator
    model = await coordinator.controller.get_model_and_version()
    if not model.model_info.max_programs:
        return

    schedule_coordinator = hass.data[DOMAIN][config_entry.entry_id].schedule_coordinator
    async_add_entities(
        [
            RainBirdCalendarEntity(
                schedule_coordinator,
                coordinator.serial_number,
                coordinator.device_info,
            )
        ]
    )


class RainBirdCalendarEntity(
    CoordinatorEntity[RainbirdScheduleUpdateCoordinator], CalendarEntity
):
    """A calendar event entity."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:sprinkler"

    def __init__(
        self,
        coordinator: RainbirdScheduleUpdateCoordinator,
        serial_number: str,
        device_info: DeviceInfo,
    ) -> None:
        """Create the Calendar event device."""
        super().__init__(coordinator)
        self._event: CalendarEvent | None = None
        self._attr_unique_id = serial_number
        self._attr_device_info = device_info

    @property
    def should_poll(self) -> bool:
        """Enable polling for the entity.

        The coordinator has its own polling interval for querying the calendar,
        and this entity updates its own state more frequently (e.g. to update when
        an event starts).
        """
        return True

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        schedule = self.coordinator.data
        if not schedule:
            raise HomeAssistantError(
                "Unable to get events: No data from controller yet"
            )
        cursor = schedule.timeline_tz(dt_util.DEFAULT_TIME_ZONE).overlapping(
            dt_util.as_local(start_date), dt_util.as_local(end_date)
        )
        return [
            CalendarEvent(
                summary=program_event.program_id.name,
                start=dt_util.as_local(program_event.start),
                end=dt_util.as_local(program_event.end),
                rrule=program_event.rrule_str,
            )
            for program_event in cursor
        ]

    def _apply_coordinator_update(self) -> None:
        """Copy state from the coordinator to this entity."""
        schedule = self.coordinator.data
        if not schedule:
            _LOGGER.debug("No schedule")
            self._event = None
            return
        cursor = schedule.timeline_tz(dt_util.DEFAULT_TIME_ZONE).active_after(
            dt_util.now()
        )
        program_event = next(cursor, None)
        if not program_event:
            _LOGGER.debug("No program event")
            self._event = None
            return
        _LOGGER.debug("Event=%s", program_event.start)
        self._event = CalendarEvent(
            summary=program_event.program_id.name,
            start=dt_util.as_local(program_event.start),
            end=dt_util.as_local(program_event.end),
            rrule=program_event.rrule_str,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._apply_coordinator_update()
        super()._handle_coordinator_update()

    async def async_update(self) -> None:
        """Disable update behavior.

        This disables the parent class behavior that asks the update coordinator to refresh.
        The coordinator itself updates at a slower pace (actually sending device RPCs) and
        this entity also updates itself to advance the clock and check if the next upcoming
        event is active. We don't call the update cordinator here, but do allow the calendar
        event state updates to happen that evaluate `event`.
        """

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # We do not ask for an update with async_add_entities()
        # because it will update disabled entities. This is started as a
        # task to let it sync in the background without blocking startup
        async def refresh() -> None:
            await self.coordinator.async_request_refresh()
            self._apply_coordinator_update()

        self.coordinator.config_entry.async_create_background_task(
            self.hass, refresh(), "rainbird.calendar-refresh"
        )
