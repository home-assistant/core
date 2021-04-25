"""Support for Aurora Forecast sensor."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import PERCENTAGE

from . import AuroraEntity
from .const import COORDINATOR, DOMAIN


async def async_setup_entry(hass, entry, async_add_entries):
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

    @property
    def state(self):
        """Return % chance the aurora is visible."""
        return self.coordinator.data

    @property
    def unit_of_measurement(self):
        """Return the unit of measure."""
        return PERCENTAGE
