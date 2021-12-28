"""Support for displaying the current CPU speed."""
from cpuinfo import cpuinfo
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME, FREQUENCY_GIGAHERTZ
import homeassistant.helpers.config_validation as cv

ATTR_BRAND = "brand"
ATTR_HZ = "ghz_advertised"
ATTR_ARCH = "arch"

HZ_ACTUAL = "hz_actual"
HZ_ADVERTISED = "hz_advertised"

DEFAULT_NAME = "CPU speed"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the CPU speed sensor."""
    name = config[CONF_NAME]
    add_entities([CpuSpeedSensor(name)], True)


class CpuSpeedSensor(SensorEntity):
    """Representation of a CPU sensor."""

    _attr_native_unit_of_measurement = FREQUENCY_GIGAHERTZ
    _attr_icon = "mdi:pulse"

    def __init__(self, name):
        """Initialize the CPU sensor."""
        self._attr_name = name
        self.info = None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.info is not None:
            attrs = {
                ATTR_ARCH: self.info["arch_string_raw"],
                ATTR_BRAND: self.info["brand_raw"],
            }
            if HZ_ADVERTISED in self.info:
                attrs[ATTR_HZ] = round(self.info[HZ_ADVERTISED][0] / 10 ** 9, 2)
            return attrs

    def update(self):
        """Get the latest data and updates the state."""
        self.info = cpuinfo.get_cpu_info()
        if HZ_ACTUAL in self.info:
            self._attr_native_value = round(float(self.info[HZ_ACTUAL][0]) / 10 ** 9, 2)
        else:
            self._attr_native_value = None
