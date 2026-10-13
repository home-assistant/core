"""Dyson Infrared integration for Home Assistant."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_DEVICE_TYPE, DOMAIN, DysonDeviceType

PLATFORMS = [Platform.CLIMATE, Platform.FAN]

PLATFORM_BY_DEVICE_TYPE: dict[DysonDeviceType, Platform] = {
    DysonDeviceType.FAN: Platform.FAN,
    DysonDeviceType.HEATER_COOLER: Platform.CLIMATE,
}


def _platform_for_entry(entry: ConfigEntry) -> Platform:
    """Return the platform serving the entry's device type."""
    stored_device_type: str = entry.data.get(CONF_DEVICE_TYPE, "")
    try:
        device_type = DysonDeviceType(stored_device_type)
    except ValueError as err:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unknown_device_type",
            translation_placeholders={"device_type": stored_device_type},
        ) from err

    return PLATFORM_BY_DEVICE_TYPE[device_type]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dyson Infrared from a config entry."""
    await hass.config_entries.async_forward_entry_setups(
        entry, [_platform_for_entry(entry)]
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Dyson Infrared config entry."""
    return await hass.config_entries.async_unload_platforms(
        entry, [_platform_for_entry(entry)]
    )
