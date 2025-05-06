"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""

from datetime import timedelta

from freebox_api.exceptions import HttpRequestError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, PLATFORMS
from .router import FreeboxRouter, get_api

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Freebox entry."""
    api = await get_api(hass, entry.data[CONF_HOST])
    try:
        await api.open(entry.data[CONF_HOST], entry.data[CONF_PORT])
    except HttpRequestError as err:
        raise ConfigEntryNotReady from err

    freebox_config = await api.system.get_config()

    router = FreeboxRouter(hass, entry, api, freebox_config)
    await router.update_all()
    entry.async_on_unload(
        async_track_time_interval(hass, router.update_all, SCAN_INTERVAL)
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = router

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_close_connection(event: Event) -> None:
        """Close Freebox connection on HA Stop."""
        await router.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        router: FreeboxRouter = hass.data[DOMAIN].pop(entry.unique_id)
        await router.close()

    return unload_ok
