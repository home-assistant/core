"""The yamaha component."""

from __future__ import annotations

import logging

import rxv

from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_MODEL, CONF_SERIAL, DOMAIN
from .yamaha_config_info import YamahaConfigInfo

PLATFORMS = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)


async def get_upnp_serial_and_model(hass: HomeAssistant, host: str):
    """Get the upnp serial and model for a given host, using the SSPD scanner."""
    ssdp_entries = await ssdp.async_get_discovery_info_by_st(hass, "upnp:rootdevice")
    matches = [w for w in ssdp_entries if w.ssdp_headers.get("_host", "") == host]
    upnp_serial = None
    model = None
    for match in matches:
        if match.ssdp_location:
            upnp_serial = match.upnp[ssdp.ATTR_UPNP_SERIAL]
            model = match.upnp[ssdp.ATTR_UPNP_MODEL_NAME]
            break

    if upnp_serial is None:
        _LOGGER.warning(
            "Could not find serial from SSDP, attempting to retrieve serial from SSDP description URL"
        )
        upnp_serial, model = await YamahaConfigInfo.get_upnp_serial_and_model(host, async_get_clientsession(hass))
    return upnp_serial, model


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Yamaha from a config entry."""
    if entry.data.get(CONF_NAME) is None:
        upnp, model = await get_upnp_serial_and_model(hass, entry.data[CONF_HOST])
        hass.config_entries.async_update_entry(
            entry,
            data={
                CONF_HOST: entry.data[CONF_HOST],
                CONF_SERIAL: entry.data[CONF_SERIAL],
                CONF_NAME: upnp[ssdp.ATTR_UPNP_MODEL_NAME],
                CONF_MODEL: entry.data[CONF_MODEL],
            },
        )

    hass.data.setdefault(DOMAIN, {})
    info = YamahaConfigInfo(entry.data[CONF_HOST])
    hass.data[DOMAIN][entry.entry_id] = await hass.async_add_executor_job( rxv.RXV, info.ctrl_url, entry.data[CONF_MODEL], entry.data[CONF_SERIAL] )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
