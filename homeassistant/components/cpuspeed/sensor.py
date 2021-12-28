"""Support for displaying the current CPU speed."""
from __future__ import annotations

from typing import Any

from cpuinfo import cpuinfo
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME, FREQUENCY_GIGAHERTZ
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

ATTR_BRAND = "brand"
ATTR_HZ = "ghz_advertised"
ATTR_ARCH = "arch"

HZ_ACTUAL = "hz_actual"
HZ_ADVERTISED = "hz_advertised"

DEFAULT_NAME = "CPU speed"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the CPU speed sensor."""
    name = config[CONF_NAME]
    async_add_entities([CpuSpeedSensor(name)], True)


class CpuSpeedSensor(SensorEntity):
    """Representation of a CPU sensor."""

    _attr_native_unit_of_measurement = FREQUENCY_GIGAHERTZ
    _attr_icon = "mdi:pulse"

    def __init__(self, name: str) -> None:
        """Initialize the CPU sensor."""
        self._attr_name = name
        self.info: dict[str, Any] | None = None

    @property
    def extra_state_attributes(self) -> dict[str, float | str | None] | None:
        """Return the state attributes."""
        if self.info is None:
            return None

        attrs = {
            ATTR_ARCH: self.info["arch_string_raw"],
            ATTR_BRAND: self.info["brand_raw"],
        }
        if HZ_ADVERTISED in self.info:
            attrs[ATTR_HZ] = round(self.info[HZ_ADVERTISED][0] / 10 ** 9, 2)
        return attrs

    def update(self) -> None:
        """Get the latest data and updates the state."""
        self.info = cpuinfo.get_cpu_info()
        if self.info is not None and HZ_ACTUAL in self.info:
            self._attr_native_value = round(float(self.info[HZ_ACTUAL][0]) / 10 ** 9, 2)
        else:
            self._attr_native_value = None
