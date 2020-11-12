"""Support for Aurora Forecast sensor."""
import logging

from homeassistant.const import PERCENTAGE

from . import AuroraEntity
from .const import COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entries):
    """Set up the binary_sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    name = f"{coordinator.name} Aurora Visibility %"

    entity = AuroraSensor(
        coordinator=coordinator,
        name=name,
        icon="mdi:gauge",
    )

    async_add_entries([entity])


class AuroraSensor(AuroraEntity):
    """Implementation of an aurora sensor."""

    @property
    def state(self):
        """Return % chance the aurora is visible."""
        return self.coordinator.data

    @property
    def unit_of_measurement(self):
        """Return the unit of measure."""
        return PERCENTAGE
