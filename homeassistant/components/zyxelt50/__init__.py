"""Support for Zyxel functions."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback

from .const import DATA_ZYXEL, DOMAIN, PLATFORMS
from .router import Zyxel_T50_Router


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zyxel from config entry."""
    router = Zyxel_T50_Router(hass, entry)
    await router.setup()

    router.async_on_close(entry.add_update_listener(update_listener))

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def async_close_connection(event):
        """Close Zyxel connection on HA Stop."""
        await router.perform_logout()

    stop_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, async_close_connection
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_ZYXEL: router,
        "stop_listener": stop_listener,
    }

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Zyxel config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN][entry.entry_id]["stop_listener"]()
        router = hass.data[DOMAIN][entry.entry_id][DATA_ZYXEL]
        await router.close()

        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Update when config_entry options update."""
    router = hass.data[DOMAIN][entry.entry_id][DATA_ZYXEL]

    if router.update_options(entry.options):
        await hass.config_entries.async_reload(entry.entry_id)
