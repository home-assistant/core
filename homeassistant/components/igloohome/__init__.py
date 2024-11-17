"""The igloohome integration."""

from __future__ import annotations

from igloohome_api import Api, Auth

from homeassistant.components.hassio import async_get_clientsession
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import HomeAssistant

# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR]

type IgloohomeConfigEntry = ConfigEntry[Api]


async def async_setup_entry(hass: HomeAssistant, entry: IgloohomeConfigEntry) -> bool:
    """Set up igloohome from a config entry."""

    session = async_get_clientsession(hass)
    authentication = Auth(
        session=session,
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
    )

    entry.runtime_data = Api(auth=authentication)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IgloohomeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
