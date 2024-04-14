"""The AirTouch4 integration."""

from airtouch4pyapi import AirTouch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import AirtouchDataUpdateCoordinator

PLATFORMS = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AirTouch4 from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    airtouch = AirTouch(host)
    await airtouch.UpdateInfo()
    info = airtouch.GetAcs()
    if not info:
        raise ConfigEntryNotReady
    coordinator = AirtouchDataUpdateCoordinator(hass, airtouch)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
