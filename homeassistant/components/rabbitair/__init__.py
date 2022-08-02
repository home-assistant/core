"""The Rabbit Air integration."""
from __future__ import annotations

from rabbitair import Client, UdpClient

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import RabbitAirDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.FAN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rabbit Air from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    host: str = entry.data[CONF_HOST]
    token: str = entry.data[CONF_ACCESS_TOKEN]

    zeroconf_instance = await zeroconf.async_get_async_instance(hass)
    device: Client = UdpClient(host, token, zeroconf=zeroconf_instance)

    coordinator = RabbitAirDataUpdateCoordinator(hass, device)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
