"""The WMS WebControl pro API integration."""

from pathlib import Path
import shutil

import aiohttp
from wmspro.webcontrol import WebControlPro

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC as MAC
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import UNDEFINED

from .const import DOMAIN, MANUFACTURER

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.COVER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SWITCH,
]

type WebControlProConfigEntry = ConfigEntry[WebControlPro]


async def async_setup_entry(
    hass: HomeAssistant, entry: WebControlProConfigEntry
) -> bool:
    """Set up wmspro from a config entry."""
    host = entry.data[CONF_HOST]
    session = async_get_clientsession(hass)
    config_dir = Path(hass.config.path(STORAGE_DIR, f"{DOMAIN}-{entry.entry_id}"))
    config_dir.mkdir(parents=True, exist_ok=True)
    hub = WebControlPro(host, session, str(config_dir))

    try:
        await hub.ping()
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(f"Error while connecting to {host}") from err

    entry.runtime_data = hub

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(MAC, entry.unique_id)} if entry.unique_id else UNDEFINED,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=MANUFACTURER,
        model="WMS WebControl pro",
        configuration_url=f"http://{hub.host}/system",
    )

    try:
        await hub.refresh()
        for dest in hub.dests.values():
            await dest.refresh()
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(f"Error while refreshing from {host}") from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: WebControlProConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant, entry: WebControlProConfigEntry
) -> None:
    """Remove a config entry."""
    config_dir = Path(hass.config.path(STORAGE_DIR, f"{DOMAIN}-{entry.entry_id}"))
    if config_dir.is_dir() and config_dir.name.startswith(DOMAIN):
        await hass.async_add_executor_job(shutil.rmtree, config_dir)
