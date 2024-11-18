"""The WiLight integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .parent_device import WiLightParent

# List the platforms that you want to support.
PLATFORMS = [Platform.COVER, Platform.FAN, Platform.LIGHT, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a wilight config entry."""

    parent = WiLightParent(hass, entry)

    if not await parent.async_setup():
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = parent

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload WiLight config entry."""

    # Unload entities for this entry/device.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Cleanup
    parent = hass.data[DOMAIN][entry.entry_id]
    await parent.async_reset()
    del hass.data[DOMAIN][entry.entry_id]

    return unload_ok
