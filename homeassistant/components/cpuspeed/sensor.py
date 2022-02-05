"""Support for displaying the current CPU speed."""
from __future__ import annotations

from cpuinfo import cpuinfo
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, FREQUENCY_GIGAHERTZ
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, LOGGER

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
    LOGGER.warning(
        "Configuration of the CPU Speed platform in YAML is deprecated and will be "
        "removed in Home Assistant 2022.4; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_NAME: config[CONF_NAME]},
        )
    )


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
                ATTR_ARCH: info["arch_string_raw"],
                ATTR_BRAND: info["brand_raw"],
            }
            if HZ_ADVERTISED in info:
                self._attr_extra_state_attributes[ATTR_HZ] = round(
                    info[HZ_ADVERTISED][0] / 10**9, 2
                )
