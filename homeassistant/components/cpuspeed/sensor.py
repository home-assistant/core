"""Support for displaying the current CPU speed."""
import logging

from cpuinfo import cpuinfo
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, FREQUENCY_GIGAHERTZ
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_BRAND = "Brand"
ATTR_HZ = "GHz Advertised"
ATTR_ARCH = "arch"

HZ_ACTUAL_RAW = "hz_actual_raw"
HZ_ADVERTISED_RAW = "hz_advertised_raw"

DEFAULT_NAME = "CPU speed"

ICON = "mdi:pulse"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the CPU speed sensor."""
    name = config.get(CONF_NAME)

    add_entities([CpuSpeedSensor(name)], True)


class CpuSpeedSensor(Entity):
    """Representation of a CPU sensor."""

    def __init__(self, name):
        """Initialize the sensor."""
        self._name = name
        self._state = None
        self.info = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return FREQUENCY_GIGAHERTZ

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.info is not None:
            attrs = {ATTR_ARCH: self.info["arch"], ATTR_BRAND: self.info["brand"]}

            if HZ_ADVERTISED_RAW in self.info:
                attrs[ATTR_HZ] = round(self.info[HZ_ADVERTISED_RAW][0] / 10 ** 9, 2)
            return attrs

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data and updates the state."""

        self.info = cpuinfo.get_cpu_info()
        if HZ_ACTUAL_RAW in self.info:
            self._state = round(float(self.info[HZ_ACTUAL_RAW][0]) / 10 ** 9, 2)
        else:
            self._state = None
