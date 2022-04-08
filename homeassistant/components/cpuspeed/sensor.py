"""Support for displaying the current CPU speed."""
from __future__ import annotations

from cpuinfo import cpuinfo

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import FREQUENCY_GIGAHERTZ
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

ATTR_BRAND = "brand"
ATTR_HZ = "ghz_advertised"
ATTR_ARCH = "arch"

HZ_ACTUAL = "hz_actual"
HZ_ADVERTISED = "hz_advertised"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""
    async_add_entities([CPUSpeedSensor(entry)], True)


class CPUSpeedSensor(SensorEntity):
    """Representation of a CPU sensor."""

    _attr_icon = "mdi:pulse"
    _attr_name = "CPU Speed"
    _attr_native_unit_of_measurement = FREQUENCY_GIGAHERTZ

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the CPU sensor."""
        self._attr_unique_id = entry.entry_id

    def update(self) -> None:
        """Get the latest data and updates the state."""
        info = cpuinfo.get_cpu_info()

        if info and HZ_ACTUAL in info:
            self._attr_native_value = round(float(info[HZ_ACTUAL][0]) / 10**9, 2)
        else:
            self._attr_native_value = None

        if info:
            self._attr_extra_state_attributes = {
                ATTR_ARCH: info.get("arch_string_raw"),
                ATTR_BRAND: info.get("brand_raw"),
            }
            if HZ_ADVERTISED in info:
                self._attr_extra_state_attributes[ATTR_HZ] = round(
                    info[HZ_ADVERTISED][0] / 10**9, 2
                )
