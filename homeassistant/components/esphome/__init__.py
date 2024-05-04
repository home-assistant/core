"""Support for esphome devices."""

from __future__ import annotations

from aioesphomeapi import APIClient

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    __version__ as ha_version,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_NOISE_PSK, DOMAIN
from .dashboard import async_setup as async_setup_dashboard
from .domain_data import DomainData

# Import config flow so that it's added to the registry
from .entry_data import RuntimeEntryData
from .manager import ESPHomeManager, cleanup_instance

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the esphome component."""
    await async_setup_dashboard(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the esphome component."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    password = entry.data[CONF_PASSWORD]
    noise_psk = entry.data.get(CONF_NOISE_PSK)

    zeroconf_instance = await zeroconf.async_get_instance(hass)

    cli = APIClient(
        host,
        port,
        password,
        client_info=f"Home Assistant {ha_version}",
        zeroconf_instance=zeroconf_instance,
        noise_psk=noise_psk,
    )

    domain_data = DomainData.get(hass)
    entry_data = RuntimeEntryData(
        client=cli,
        entry_id=entry.entry_id,
        title=entry.title,
        store=domain_data.get_or_create_store(hass, entry),
        original_options=dict(entry.options),
    )
    domain_data.set_entry_data(entry, entry_data)

    manager = ESPHomeManager(
        hass, entry, host, password, cli, zeroconf_instance, domain_data, entry_data
    )
    await manager.async_start()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an esphome config entry."""
    entry_data = await cleanup_instance(hass, entry)
    return await hass.config_entries.async_unload_platforms(
        entry, entry_data.loaded_platforms
    )


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove an esphome config entry."""
    await DomainData.get(hass).get_or_create_store(hass, entry).async_remove()
