import datetime
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .coordinator import SwitchgridCoordinator

_LOGGER = logging.getLogger(__name__)


UtcTzInfo = datetime.UTC


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar platform for entity."""
    _LOGGER.debug("async_setup_entry")
    coordinator: SwitchgridCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([SwitchgridCalendarEntity(coordinator)])


class SwitchgridCalendarEntity(
    CoordinatorEntity[SwitchgridCoordinator], CalendarEntity
):
    """A calendar entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "calendar"
    _attr_name = "Switchgrid"
    # _attr_icon = "mdi:lightning-bolt"
    # _attr_unique_id = "switchgrid_calendar"
    _attr_entity_picture = "https://app.switchgrid.tech/circular-sg-logo.png"
    _events: list[CalendarEvent] = []

    def __init__(self, coordinator: SwitchgridCoordinator) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        _LOGGER.debug("calendar init")

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next (first) upcoming event."""
        _LOGGER.debug("getting single event")

        now = datetime.datetime.now(tz=UtcTzInfo)
        ongoing_events = list(
            filter(lambda event: event.start <= now <= event.end, self._events)
        )
        return ongoing_events[0] if len(ongoing_events) > 0 else None

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        _LOGGER.debug("device_info")
        _LOGGER.warning(self._config_entry)
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name="Switchgrid",
            manufacturer="Switchgrid",
            model="Switchgrid",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(self.coordinator.data)
        self._events = list(
            map(
                lambda period: CalendarEvent(
                    datetime.datetime.fromisoformat(period["startUtc"]),
                    datetime.datetime.fromisoformat(period["endUtc"]),
                    period["command"],
                ),
                self.coordinator.data[0]["periods"],  # Todo map on all elements
            )
        )
        _LOGGER.debug("updated events to")
        _LOGGER.debug(self._events)

        self.async_write_ha_state()

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        # maps self._events to CalendarEvent

        _LOGGER.debug("async_get_events", self._events)
        return self._events
