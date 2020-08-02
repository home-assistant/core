"""Tracks the latency of a host by sending ICMP echo requests (ping)."""
from datetime import timedelta
import logging

from icmplib import ping as icmp_ping
import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import CONF_HOST, CONF_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_ROUND_TRIP_TIME_AVG = "round_trip_time_avg"
ATTR_ROUND_TRIP_TIME_MAX = "round_trip_time_max"
ATTR_PACKET_LOSS = "packet_loss"
ATTR_ROUND_TRIP_TIME_MIN = "round_trip_time_min"

CONF_PING_COUNT = "count"

DEFAULT_NAME = "Ping"
DEFAULT_PING_COUNT = 5
DEFAULT_DEVICE_CLASS = "connectivity"

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_PING_COUNT, default=DEFAULT_PING_COUNT): vol.Range(
            min=1, max=60
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ping Binary sensor."""
    host = config[CONF_HOST]
    count = config[CONF_PING_COUNT]
    name = config.get(CONF_NAME, f"{DEFAULT_NAME} {host}")

    add_entities([PingBinarySensor(name, PingData(host, count))], True)


class PingBinarySensor(BinarySensorEntity):
    """Representation of a Ping Binary sensor."""

    def __init__(self, name, ping):
        """Initialize the Ping Binary sensor."""
        self._name = name
        self.ping = ping

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return DEFAULT_DEVICE_CLASS

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.ping.available

    @property
    def device_state_attributes(self):
        """Return the state attributes of the ICMP echo request."""
        if self.ping.data is not False:
            return {
                ATTR_ROUND_TRIP_TIME_AVG: self.ping.data["avg"],
                ATTR_ROUND_TRIP_TIME_MAX: self.ping.data["max"],
                ATTR_ROUND_TRIP_TIME_MIN: self.ping.data["min"],
                ATTR_PACKET_LOSS: self.ping.data["packet_loss"],
            }

    def update(self):
        """Get the latest data."""
        self.ping.update()


class PingData:
    """The Class for handling the data retrieval."""

    def __init__(self, host, count):
        """Initialize the data object."""
        self._ip_address = host
        self._count = count
        self.data = {}
        self.available = False

    def ping(self):
        """Send ICMP echo request and return details if success."""
        host = icmp_ping(self._ip_address, count=self._count, interval=1, timeout=2)
        return {
            "alive": host.is_alive,
            "min": host.min_rtt,
            "avg": host.avg_rtt,
            "max": host.max_rtt,
            "packet_loss": host.packet_loss,
        }

    def update(self):
        """Retrieve the latest details from the host."""
        self.data = self.ping()
        self.available = self.data and self.data["alive"]
