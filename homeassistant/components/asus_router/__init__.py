"""Native support for Asus wireless routers using HTTP(S) API."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS, ROUTER, STOP_LISTENER
from .router import ARDevice


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> bool:
    """Set up Asus Router platform."""

    router = ARDevice(hass, config_entry)
    await router.setup()

    router.async_on_close(config_entry.add_update_listener(update_listener))

    async def async_close_connection(event):
        """Close router connection of HA stop."""

        await router.close()

    stop_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, async_close_connection
    )

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        ROUTER: router,
        STOP_LISTENER: stop_listener,
    }

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> bool:
    """Unload Asus Router config entry."""

    unload = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

    if unload:
        # Close connection
        hass.data[DOMAIN][config_entry.entry_id][STOP_LISTENER]()
        await hass.data[DOMAIN][config_entry.entry_id][ROUTER].close()
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload


async def update_listener(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    """Reload on config entry update."""

    router = hass.data[DOMAIN][config_entry.entry_id][ROUTER]

    if router.update_options(config_entry.options):
        await hass.config_entries.async_reload(config_entry.entry_id)

    return
