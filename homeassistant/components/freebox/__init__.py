"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""

from datetime import timedelta

from freebox_api.exceptions import HttpRequestError

from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, PLATFORMS
from .router import FreeboxConfigEntry, FreeboxRouter, get_api

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, entry: FreeboxConfigEntry) -> bool:
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

    entry.runtime_data = router

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_close_connection(event: Event) -> None:
        """Close Freebox connection on HA Stop."""
        await router.close()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )
    entry.async_on_unload(router.close)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FreeboxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: FreeboxConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove a config entry from a device."""
    router = config_entry.runtime_data
    router_mac = dr.format_mac(router.mac)

    # Never allow removal of the Freebox router itself. Persisted identifiers
    # may pre-date MAC normalisation, so compare the format_mac()-normalised
    # value of every (DOMAIN, …) identifier rather than the raw one.
    for domain, identifier in device_entry.identifiers:
        if domain == DOMAIN and dr.format_mac(identifier) == router_mac:
            return False
    if (dr.CONNECTION_NETWORK_MAC, router_mac) in device_entry.connections:
        return False

    # Block removal of device-tracker entries whose MAC is still on the LAN.
    for connection_type, connection_value in device_entry.connections:
        if (
            connection_type == dr.CONNECTION_NETWORK_MAC
            and connection_value in router.devices
        ):
            return False

    return True
