"""Support for Streamlabs Water Monitor Away Mode."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import StreamlabsCoordinator
from .const import DOMAIN
from .coordinator import StreamlabsData

NAME_AWAY_MODE = "Water Away Mode"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Streamlabs water binary sensor from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    for location_id in coordinator.data:
        entities.append(StreamlabsAwayMode(coordinator, location_id))

    async_add_entities(entities)


class StreamlabsAwayMode(CoordinatorEntity[StreamlabsCoordinator], BinarySensorEntity):
    """Monitor the away mode state."""

    def __init__(self, coordinator: StreamlabsCoordinator, location_id: str) -> None:
        """Initialize the away mode device."""
        super().__init__(coordinator)
        self._location_id = location_id

    @property
    def location_data(self) -> StreamlabsData:
        """Returns the data object."""
        return self.coordinator.data[self._location_id]

    @property
    def name(self) -> str:
        """Return the name for away mode."""
        return f"{self.location_data.name} {NAME_AWAY_MODE}"

    @property
    def is_on(self) -> bool:
        """Return if away mode is on."""
        return self.location_data.is_away
