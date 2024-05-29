"""The Aladdin Connect Genie integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import api
from .const import CONFIG_FLOW_MINOR_VERSION, CONFIG_FLOW_VERSION

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aladdin Connect Genie from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    # If using an aiohttp-based API lib
    entry.runtime_data = api.AsyncConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), session
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config."""
    if config_entry.version < CONFIG_FLOW_VERSION:
        config_entry.async_start_reauth(hass)
        new_data = {**config_entry.data}
        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            version=CONFIG_FLOW_VERSION,
            minor_version=CONFIG_FLOW_MINOR_VERSION,
        )

    return True
