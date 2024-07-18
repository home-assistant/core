"""Зrovides the implementation of the Lviv PowerOff calendar."""

import datetime
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import LvivPowerOffCoordinator

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Yasno outages calendar platform."""
    LOGGER.debug("Setup new entry: %s", config_entry)
    coordinator: LvivPowerOffCoordinator = config_entry.runtime_data
    async_add_entities([LvivPowerOffCalendar(coordinator)])


class LvivPowerOffCalendar(CalendarEntity):
    """Implementation of calendar entity."""

    def __init__(
        self,
        coordinator: LvivPowerOffCoordinator,
    ) -> None:
        """Initialize the LvivPowerOffCoordinator entity."""
        super().__init__()
        self.coordinator = coordinator
        self.entity_description = EntityDescription(
            key="calendar",
            name="Lviv PowerOff Calendar",
        )
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-"
            f"{coordinator.group}-"
            f"{self.entity_description.key}"
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event or None."""
        now = dt_util.now()
        LOGGER.debug("Getting current event for %s", now)
        return self.coordinator.get_event_at(now)

    async def async_get_events(
        self,
        hass: HomeAssistant,  # noqa: ARG002
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        LOGGER.debug('Getting all events between "%s" -> "%s"', start_date, end_date)
        return self.coordinator.get_events_between(start_date, end_date)
