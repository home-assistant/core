"""Support for getting status from a Pi-hole system."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_NAME

from . import PiHoleEntity
from .const import DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN as PIHOLE_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Pi-hole binary sensor."""
    name = entry.data[CONF_NAME]
    hole_data = hass.data[PIHOLE_DOMAIN][entry.entry_id]
    binary_sensors = [
        PiHoleBinarySensor(
            hole_data[DATA_KEY_API],
            hole_data[DATA_KEY_COORDINATOR],
            name,
            entry.entry_id,
        )
    ]
    async_add_entities(binary_sensors, True)


class PiHoleBinarySensor(PiHoleEntity, BinarySensorEntity):
    """Representation of a Pi-hole binary sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._server_unique_id}/Status"

    @property
    def is_on(self):
        """Return if the service is on."""
        return self.api.data.get("status") == "enabled"
