"""The FiveM binary sensor platform."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FiveMDataUpdateCoordinator, FiveMEntity
from .const import DOMAIN, ICON_STATUS, NAME_STATUS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the FiveM binary sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([FiveMStatusBinarySensor(coordinator)])


class FiveMSensorEntity(FiveMEntity, BinarySensorEntity):
    """Representation of a FiveM sensor base entity."""

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.coordinator.data[self.type_name]


class FiveMStatusBinarySensor(FiveMSensorEntity):
    """Representation of a FiveM status binary sensor."""

    def __init__(self, coordinator: FiveMDataUpdateCoordinator) -> None:
        """Initialize status binary sensor."""
        super().__init__(
            coordinator, NAME_STATUS, ICON_STATUS, BinarySensorDeviceClass.CONNECTIVITY
        )
