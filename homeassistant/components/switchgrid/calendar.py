import datetime
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .coordinator import SwitchgridCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar platform for entity."""
    coordinator: SwitchgridCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([SwitchgridCalendarEntity(coordinator, config_entry)])


class SwitchgridCalendarEntity(
    CoordinatorEntity[SwitchgridCoordinator], CalendarEntity
):
    _attr_has_entity_name = True
    _attr_translation_key = "switchgrid_events"
    _events: list[CalendarEvent] = []

    def __init__(
        self, coordinator: SwitchgridCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = "switchgrid_events"
        self._config_entry = config_entry

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next (first) upcoming event."""
        now = dt_util.now()
        ongoing_events = list(filter(lambda event: now <= event.start, self._events))
        return ongoing_events[0] if len(ongoing_events) > 0 else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(self.coordinator.data)
        self._events = list(
            map(
                lambda event: CalendarEvent(
                    start=event["startUtc"],
                    end=event["endUtc"],
                    summary=event["summary"],
                    description=event["description"],
                ),
                self.coordinator.data["events"],
            )
        )
        self.async_write_ha_state()

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        return list(
            filter(
                lambda event: start_date <= event.start <= end_date
                or start_date <= event.end <= end_date,
                self._events,
            )
        )
