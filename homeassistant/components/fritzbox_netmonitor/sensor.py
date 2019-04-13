"""Support for monitoring an AVM Fritz!Box router."""
import logging
from datetime import timedelta
from requests.exceptions import RequestException

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_HOST, STATE_UNAVAILABLE)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_DEFAULT_NAME = 'fritz_netmonitor'
CONF_DEFAULT_IP = '169.254.1.1'  # This IP is valid for all FRITZ!Box routers.

ATTR_BYTES_RECEIVED = 'bytes_received'
ATTR_BYTES_SENT = 'bytes_sent'
ATTR_TRANSMISSION_RATE_UP = 'transmission_rate_up'
ATTR_TRANSMISSION_RATE_DOWN = 'transmission_rate_down'
ATTR_EXTERNAL_IP = 'external_ip'
ATTR_IS_CONNECTED = 'is_connected'
ATTR_IS_LINKED = 'is_linked'
ATTR_MAX_BYTE_RATE_DOWN = 'max_byte_rate_down'
ATTR_MAX_BYTE_RATE_UP = 'max_byte_rate_up'
ATTR_UPTIME = 'uptime'
ATTR_WAN_ACCESS_TYPE = 'wan_access_type'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

STATE_ONLINE = 'online'
STATE_OFFLINE = 'offline'

ICON = 'mdi:web'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=CONF_DEFAULT_NAME): cv.string,
    vol.Optional(CONF_HOST, default=CONF_DEFAULT_IP): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the FRITZ!Box monitor sensors."""
    # pylint: disable=import-error
    import fritzconnection as fc
    from fritzconnection.fritzconnection import FritzConnectionException

    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)

    try:
        fstatus = fc.FritzStatus(address=host)
    except (ValueError, TypeError, FritzConnectionException):
        fstatus = None

    if fstatus is None:
        _LOGGER.error("Failed to establish connection to FRITZ!Box: %s", host)
        return 1
    _LOGGER.info("Successfully connected to FRITZ!Box")

    add_entities([FritzboxMonitorSensor(name, fstatus)], True)


class FritzboxMonitorSensor(Entity):
    """Implementation of a fritzbox monitor sensor."""

    def __init__(self, name, fstatus):
        """Initialize the sensor."""
        self._name = name
        self._fstatus = fstatus
        self._state = STATE_UNAVAILABLE
        self._is_linked = self._is_connected = self._wan_access_type = None
        self._external_ip = self._uptime = None
        self._bytes_sent = self._bytes_received = None
        self._transmission_rate_up = None
        self._transmission_rate_down = None
        self._max_byte_rate_up = self._max_byte_rate_down = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name.rstrip()

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
        attr = {
            ATTR_IS_LINKED: self._is_linked,
            ATTR_IS_CONNECTED: self._is_connected,
            ATTR_WAN_ACCESS_TYPE: self._wan_access_type,
            ATTR_EXTERNAL_IP: self._external_ip,
            ATTR_UPTIME: self._uptime,
            ATTR_BYTES_SENT: self._bytes_sent,
            ATTR_BYTES_RECEIVED: self._bytes_received,
            ATTR_TRANSMISSION_RATE_UP: self._transmission_rate_up,
            ATTR_TRANSMISSION_RATE_DOWN: self._transmission_rate_down,
            ATTR_MAX_BYTE_RATE_UP: self._max_byte_rate_up,
            ATTR_MAX_BYTE_RATE_DOWN: self._max_byte_rate_down,
        }
        return attr

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Retrieve information from the FritzBox."""
        try:
            self._is_linked = self._fstatus.is_linked
            self._is_connected = self._fstatus.is_connected
            self._wan_access_type = self._fstatus.wan_access_type
            self._external_ip = self._fstatus.external_ip
            self._uptime = self._fstatus.uptime
            self._bytes_sent = self._fstatus.bytes_sent
            self._bytes_received = self._fstatus.bytes_received
            transmission_rate = self._fstatus.transmission_rate
            self._transmission_rate_up = transmission_rate[0]
            self._transmission_rate_down = transmission_rate[1]
            self._max_byte_rate_up = self._fstatus.max_byte_rate[0]
            self._max_byte_rate_down = self._fstatus.max_byte_rate[1]
            self._state = STATE_ONLINE if self._is_connected else STATE_OFFLINE
        except RequestException as err:
            self._state = STATE_UNAVAILABLE
            _LOGGER.warning("Could not reach FRITZ!Box: %s", err)
