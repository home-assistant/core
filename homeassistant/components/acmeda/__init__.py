"""The Rollease Acmeda Automate integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .hub import PulseHub

CONF_HUBS = "hubs"

PLATFORMS = [Platform.COVER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Rollease Acmeda Automate hub from a config entry."""
    hub = PulseHub(hass, config_entry)

    if not await hub.async_setup():
        return False

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = hub
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if not await hub.async_reset():
        return False

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
