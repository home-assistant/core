"""Dyson Infrared integration for Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_TYPE, DysonDeviceType

PLATFORMS = [Platform.CLIMATE, Platform.FAN]

PLATFORM_BY_DEVICE_TYPE: dict[DysonDeviceType, Platform] = {
    DysonDeviceType.FAN: Platform.FAN,
    DysonDeviceType.HEATER_COOLER: Platform.CLIMATE,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dyson Infrared from a config entry."""
    device_type = DysonDeviceType(entry.data[CONF_DEVICE_TYPE])
    await hass.config_entries.async_forward_entry_setups(
        entry, [PLATFORM_BY_DEVICE_TYPE[device_type]]
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Dyson Infrared config entry."""
    device_type = DysonDeviceType(entry.data[CONF_DEVICE_TYPE])
    return await hass.config_entries.async_unload_platforms(
        entry, [PLATFORM_BY_DEVICE_TYPE[device_type]]
    )
