"""Envertech EVT800 integration."""

import pyenvertechevt800

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import EnvertechEVT800Coordinator

type EnvertechEVT800ConfigEntry = ConfigEntry[EnvertechEVT800Coordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: EnvertechEVT800ConfigEntry
) -> bool:
    """Set up Envertech EVT800 from a config entry."""
    evt800 = pyenvertechevt800.EnvertechEVT800(
        entry.data[CONF_IP_ADDRESS], entry.data[CONF_PORT]
    )
    evt800.start()

    coordinator = EnvertechEVT800Coordinator(
        hass,
        evt800,
        entry,
    )
    coordinator.async_set_updated_data(evt800.data)
    await coordinator.async_config_entry_first_refresh()

    async def async_close_session():
        """Close the session."""
        evt800.stop()

    entry.async_on_unload(async_close_session)

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EnvertechEVT800ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        client = entry.runtime_data.client
        if hasattr(client, "stop") and callable(client.stop):
            client.stop()

    return unload_ok
