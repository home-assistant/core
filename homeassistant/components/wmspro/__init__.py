"""The WMS WebControl pro API integration."""

from __future__ import annotations

import aiohttp
from wmspro.webcontrol import WebControlPro

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, MANUFACTURER

PLATFORMS: list[Platform] = [Platform.COVER]

type WebControlProConfigEntry = ConfigEntry[WebControlPro]


async def async_setup_entry(
    hass: HomeAssistant, entry: WebControlProConfigEntry
) -> bool:
    """Set up wmspro from a config entry."""
    host = entry.data[CONF_HOST]
    session = async_get_clientsession(hass)
    hub = WebControlPro(host, session)

    try:
        await hub.ping()
        await hub.refresh()
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(f"Error while connecting to {host}") from err

    entry.runtime_data = hub

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, hub.host)},
        manufacturer=MANUFACTURER,
        name=entry.title,
        model="WMS WebControl pro",
        configuration_url=f"http://{hub.host}/system",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: WebControlProConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
