"""Support for aurora forecast data sensor."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import ATTR_NAME
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AuroraDataUpdateCoordinator
from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTRIBUTION,
    COORDINATOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entries):
    """Set up the binary_sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    name = coordinator._name

    entity = AuroraSensor(coordinator, name)

    async_add_entries([entity])


class AuroraSensor(CoordinatorEntity, BinarySensorEntity):
    """Implementation of an aurora sensor."""

    def __init__(self, coordinator: AuroraDataUpdateCoordinator, name):
        """Define the binary sensor for the Aurora integration."""
        self._name = name
        self.coordinator = coordinator

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if aurora is visible."""
        return self.coordinator.data > self.coordinator._threshold

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"attribution": ATTRIBUTION}

    @property
    def icon(self):
        """Return the icon for the sensor."""
        return "mdi:hazard-lights"

    @property
    def device_info(self):
        """Define the device based on name."""
        return {
            ATTR_IDENTIFIERS: {
                (DOMAIN, self.coordinator._name.lower().replace(" ", "_"))
            },
            ATTR_NAME: self.coordinator._name,
            ATTR_MANUFACTURER: "NOAA",
            ATTR_MODEL: "Aurora Visibility Sensor",
        }
