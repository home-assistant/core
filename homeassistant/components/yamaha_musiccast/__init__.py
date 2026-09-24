"""The MusicCast integration."""

import logging

from aiohttp import DummyCookieJar
from aiomusiccast.musiccast_device import MusicCastDevice

from homeassistant.components import ssdp
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import BRAND, CONF_SERIAL, CONF_UPNP_DESC, DEFAULT_ZONE, DOMAIN
from .coordinator import MusicCastConfigEntry, MusicCastDataUpdateCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.NUMBER, Platform.SELECT, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def get_upnp_desc(hass: HomeAssistant, host: str):
    """Get the upnp description URL for a given host, using the SSPD scanner."""
    ssdp_entries = await ssdp.async_get_discovery_info_by_st(hass, "upnp:rootdevice")
    matches = [w for w in ssdp_entries if w.ssdp_headers.get("_host", "") == host]
    upnp_desc = None
    for match in matches:
        if upnp_desc := match.ssdp_location:
            break

    if not upnp_desc:
        _LOGGER.warning(
            "The upnp_description was not found automatically, setting a default one"
        )
        upnp_desc = f"http://{host}:49154/MediaRenderer/desc.xml"
    return upnp_desc


async def async_setup_entry(hass: HomeAssistant, entry: MusicCastConfigEntry) -> bool:
    """Set up MusicCast from a config entry."""

    if entry.data.get(CONF_UPNP_DESC) is None:
        hass.config_entries.async_update_entry(
            entry,
            data={
                CONF_HOST: entry.data[CONF_HOST],
                CONF_SERIAL: entry.data["serial"],
                CONF_UPNP_DESC: await get_upnp_desc(hass, entry.data[CONF_HOST]),
            },
        )

    client = MusicCastDevice(
        entry.data[CONF_HOST],
        async_create_clientsession(hass, cookie_jar=DummyCookieJar()),
        entry.data[CONF_UPNP_DESC],
    )
    coordinator = MusicCastDataUpdateCoordinator(hass, entry, client=client)
    await coordinator.async_config_entry_first_refresh()
    coordinator.musiccast.build_capabilities()

    entry.runtime_data = coordinator

    await coordinator.musiccast.device.enable_polling()

    # Register the main device before forwarding platforms so the zone sub-devices
    # can resolve it as their via_device parent when they are added.
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, coordinator.data.device_id)},
        connections={
            (dr.CONNECTION_NETWORK_MAC, mac)
            for mac in coordinator.data.mac_addresses.values()
        },
        name=coordinator.data.zones[DEFAULT_ZONE].name,
        manufacturer=BRAND,
        model=coordinator.data.model_name,
        sw_version=str(coordinator.data.system_version),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MusicCastConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data.musiccast.device.disable_polling()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: MusicCastConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
