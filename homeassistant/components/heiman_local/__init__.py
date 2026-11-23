"""Heiman Local integration."""

from heiman_local_client import HeimanSwitchClient

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import HeimanConfigEntry, HeimanCoordinator

_PLATFORMS = (Platform.SWITCH,)


async def async_setup_entry(hass: HomeAssistant, entry: HeimanConfigEntry) -> None:
    """Set up the Wi-Fi switch from a config entry."""
    client = HeimanSwitchClient(
        async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_PORT]
    )
    coordinator = HeimanCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: HeimanConfigEntry) -> None:
    """Unload the Wi-Fi switch."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
