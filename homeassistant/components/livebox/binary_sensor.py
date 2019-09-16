"""Livebox binary sensor entities."""
from homeassistant.util import Throttle
from homeassistant.components.binary_sensor import (
    BinarySensorDevice,
    DEVICE_CLASS_CONNECTIVITY,
)

from . import DOMAIN, SCAN_INTERVAL, DATA_LIVEBOX
from .const import TEMPLATE_SENSOR


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer binary sensor setup to the shared sensor module."""
    box_data = hass.data[DOMAIN][DATA_LIVEBOX]
    id = config_entry.data["id"]
    async_add_entities([InfoSensor(box_data, id)], True)


class InfoSensor(BinarySensorDevice):
    """Representation of a livebox sensor."""

    device_class = DEVICE_CLASS_CONNECTIVITY

    def __init__(self, box_data, id):
        """Initialize the sensor."""

        self._box_data = box_data
        self._box_id = id
        self._state = None
        self._datas = None
        self._dsl = None

    @property
    def name(self):
        """Return name sensor."""

        return f"{TEMPLATE_SENSOR} Wan status"

    def is_on(self):
        """Return true if the binary sensor is on."""

        if self._dsl["WanState"] == "up":
            return True
        return False

    @property
    def unique_id(self):
        """Return unique_id."""

        return f"{self._box_id}_connectivity"

    @property
    def device_info(self):
        """Return the device info."""

        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": "Orange",
            "via_device": (DOMAIN, self._box_id),
        }

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""

        return {
            "link_type": self._dsl["LinkType"],
            "link_state": self._dsl["LinkState"],
            "last_connection_error": self._dsl["LastConnectionError"],
            "wan_ipaddress": self._dsl["IPAddress"],
            "wan_ipv6address": self._dsl["IPv6Address"],
        }

    @Throttle(SCAN_INTERVAL)
    async def async_update(self):
        """Fetch status from livebox."""

        self._dsl = await self._box_data.async_status()
