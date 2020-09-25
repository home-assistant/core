"""Support for monitoring an AVM Fritz!Box router."""


from requests.exceptions import RequestException

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import (
    ATTR_BYTES_RECEIVED,
    ATTR_BYTES_SENT,
    ATTR_EXTERNAL_IP,
    ATTR_IS_CONNECTED,
    ATTR_IS_LINKED,
    ATTR_MAX_BYTE_RATE_DOWN,
    ATTR_MAX_BYTE_RATE_UP,
    ATTR_TRANSMISSION_RATE_DOWN,
    ATTR_TRANSMISSION_RATE_UP,
    ATTR_UPTIME,
    DOMAIN,
    ICON,
    LOGGER,
    MANUFACTURER,
    MIN_TIME_BETWEEN_UPDATES,
    STATE_OFFLINE,
    STATE_ONLINE,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the fritzbox_netmonitor sensor from config_entry."""

    fritz_status, host = hass.data[DOMAIN][config_entry.entry_id]
    entities = [FritzboxMonitorSensor(fritz_status, host)]

    async_add_entities(entities, True)


class FritzboxMonitorSensor(Entity):
    """Implementation of a fritzbox_netmonitor sensor."""

    def __init__(self, fritz_status, host):
        """Initialize the sensor."""
        self._fritz_status = fritz_status
        self._host = host
        self._state = STATE_UNAVAILABLE
        self._is_linked = None
        self._is_connected = None
        self._external_ip = None
        self._uptime = None
        self._bytes_sent = None
        self._bytes_received = None
        self._transmission_rate_up = None
        self._transmission_rate_down = None
        self._max_byte_rate_up = None
        self._max_byte_rate_down = None

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self._host)},
            "manufacturer": MANUFACTURER,
            "model": self._fritz_status.modelname,
            "sw_version": self._fritz_status.fc.system_version,
        }

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return self._host

    @property
    def name(self):
        """Return the name of the device."""
        return self._fritz_status.modelname

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def state_attributes(self):
        """Return the device state attributes."""
        # Don't return attributes if FritzBox is unreachable
        if self._state == STATE_UNAVAILABLE:
            return {}
        return {
            ATTR_IS_LINKED: self._is_linked,
            ATTR_IS_CONNECTED: self._is_connected,
            ATTR_EXTERNAL_IP: self._external_ip,
            ATTR_UPTIME: self._uptime,
            ATTR_BYTES_SENT: self._bytes_sent,
            ATTR_BYTES_RECEIVED: self._bytes_received,
            ATTR_TRANSMISSION_RATE_UP: self._transmission_rate_up,
            ATTR_TRANSMISSION_RATE_DOWN: self._transmission_rate_down,
            ATTR_MAX_BYTE_RATE_UP: self._max_byte_rate_up,
            ATTR_MAX_BYTE_RATE_DOWN: self._max_byte_rate_down,
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Retrieve information from the FritzBox."""
        try:
            self._is_linked = self._fritz_status.is_linked
            self._is_connected = self._fritz_status.is_connected
            self._external_ip = self._fritz_status.external_ip
            self._uptime = self._fritz_status.uptime
            self._bytes_sent = self._fritz_status.bytes_sent
            self._bytes_received = self._fritz_status.bytes_received
            transmission_rate = self._fritz_status.transmission_rate
            self._transmission_rate_up = transmission_rate[0]
            self._transmission_rate_down = transmission_rate[1]
            self._max_byte_rate_up = self._fritz_status.max_byte_rate[0]
            self._max_byte_rate_down = self._fritz_status.max_byte_rate[1]
            self._state = STATE_ONLINE if self._is_connected else STATE_OFFLINE
        except RequestException as error:
            self._state = STATE_UNAVAILABLE
            LOGGER.warning("Could not reach FRITZ!Box (%s): %s", self._host, error)
