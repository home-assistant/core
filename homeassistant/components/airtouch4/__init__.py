"""The AirTouch4 integration."""

from airtouch4pyapi import AirTouch, AirTouchVersion

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import PORT
from .coordinator import AirTouch4ConfigEntry, AirtouchDataUpdateCoordinator

PLATFORMS = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: AirTouch4ConfigEntry) -> bool:
    """Set up AirTouch4 from a config entry."""
    host = entry.data[CONF_HOST]
    # Pass the version and port explicitly so the library does not probe for the
    # protocol version, which opens a blocking socket in the event loop.
    airtouch = AirTouch(host, AirTouchVersion.AIRTOUCH4, PORT)
    await airtouch.UpdateInfo()
    info = airtouch.GetAcs()
    if not info:
        raise ConfigEntryNotReady
    coordinator = AirtouchDataUpdateCoordinator(hass, entry, airtouch)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirTouch4ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
