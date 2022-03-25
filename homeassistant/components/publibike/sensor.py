"""Support for PubliBike Public API for bike sharing in Switzerland."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PubliBikeDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the PubliBike sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([EBikeSensor(coordinator), BikeSensor(coordinator)])


class PubliBikeSensor(CoordinatorEntity[PubliBikeDataUpdateCoordinator], SensorEntity):
    """Representation of a PubliBike sensor."""

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.attributes = {}

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self.attributes


class EBikeSensor(PubliBikeSensor):
    """Representation of an E-Bike Sensor."""

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = f"{coordinator.station.name} - E-bikes"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.coordinator.available_ebikes

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        self.attributes.update({"All E-bikes": len(self.coordinator.station.ebikes)})
        return self.attributes


class BikeSensor(PubliBikeSensor):
    """Representation of a Bike Sensor."""

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = f"{coordinator.station.name} - Bikes"

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return len(self.coordinator.station.bikes)
