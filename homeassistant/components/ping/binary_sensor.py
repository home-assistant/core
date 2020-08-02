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
ATTR_ROUND_TRIP_TIME_MIN = "round_trip_time_min"
ATTR_PACKET_LOSS_PERCENT = "packet_loss_percent"

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

    add_entities([PingBinarySensor(name, host, count)], True)


class PingBinarySensor(BinarySensorEntity):
    """Representation of a Ping Binary sensor."""

    def __init__(self, name, host, count):
        """Initialize the Ping Binary sensor."""
        self._ping = None
        self._name = name
        self._host = host
        self._count = count

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
        return self._ping and self._ping.is_alive

    @property
    def device_state_attributes(self):
        """Return the state attributes of the ICMP echo request."""
        if not self._ping.data:
            return

        return {
            ATTR_ROUND_TRIP_TIME_AVG: self._ping.avg_rtt,
            ATTR_ROUND_TRIP_TIME_MAX: self._ping.max_rtt,
            ATTR_ROUND_TRIP_TIME_MIN: self._ping.min_rtt,
            ATTR_PACKET_LOSS_PERCENT: self._ping.packet_loss * 100,
        }

    def update(self):
        """Get the latest data."""
        self._ping = icmp_ping(self._host, count=self._count)
