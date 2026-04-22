"""The Data Grand Lyon integration."""

from __future__ import annotations

from data_grand_lyon_ha import DataGrandLyonClient

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import DataGrandLyonConfigEntry, DataGrandLyonCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: DataGrandLyonConfigEntry
) -> bool:
    """Set up Data Grand Lyon from a config entry."""
    session = async_get_clientsession(hass)
    client = DataGrandLyonClient(
        session=session,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    coordinator = DataGrandLyonCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_entry(
    hass: HomeAssistant, entry: DataGrandLyonConfigEntry
) -> None:
    """Handle config entry update (e.g., subentry changes)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: DataGrandLyonConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
