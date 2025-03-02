"""The NZBGet integration."""

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_SPEED,
    DATA_COORDINATOR,
    DATA_UNDO_UPDATE_LISTENER,
    DEFAULT_SPEED_LIMIT,
    DOMAIN,
    SERVICE_PAUSE,
    SERVICE_RESUME,
    SERVICE_SET_SPEED,
)
from .coordinator import NZBGetDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR, Platform.SWITCH]


SPEED_LIMIT_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_SPEED, default=DEFAULT_SPEED_LIMIT): cv.positive_int}
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NZBGet from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = NZBGetDataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    undo_listener = entry.add_update_listener(_async_update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_UNDO_UPDATE_LISTENER: undo_listener,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_services(hass, coordinator)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN][entry.entry_id][DATA_UNDO_UPDATE_LISTENER]()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def _async_register_services(
    hass: HomeAssistant,
    coordinator: NZBGetDataUpdateCoordinator,
) -> None:
    """Register integration-level services."""

    def pause(call: ServiceCall) -> None:
        """Service call to pause downloads in NZBGet."""
        coordinator.nzbget.pausedownload()

    def resume(call: ServiceCall) -> None:
        """Service call to resume downloads in NZBGet."""
        coordinator.nzbget.resumedownload()

    def set_speed(call: ServiceCall) -> None:
        """Service call to rate limit speeds in NZBGet."""
        coordinator.nzbget.rate(call.data[ATTR_SPEED])

    hass.services.async_register(DOMAIN, SERVICE_PAUSE, pause, schema=vol.Schema({}))
    hass.services.async_register(DOMAIN, SERVICE_RESUME, resume, schema=vol.Schema({}))
    hass.services.async_register(
        DOMAIN, SERVICE_SET_SPEED, set_speed, schema=SPEED_LIMIT_SCHEMA
    )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
