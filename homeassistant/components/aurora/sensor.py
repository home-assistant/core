"""Support for Aurora Forecast sensor."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AuroraEntity
from .const import COORDINATOR, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entries: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    entity = AuroraSensor(
        coordinator=coordinator,
        name=f"{coordinator.name} Aurora Visibility %",
        icon="mdi:gauge",
    )

    async_add_entries([entity])


class AuroraSensor(AuroraEntity, SensorEntity):
    """Implementation of an aurora sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self):
        """Return % chance the aurora is visible."""
        return self.coordinator.data
