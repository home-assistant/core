"""The Goal Zero Yeti integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from goalzero import Yeti, exceptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN
from .coordinator import GoalZeroDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Goal Zero Yeti from a config entry."""

    mac = entry.unique_id

    if TYPE_CHECKING:
        assert mac is not None

    if (formatted_mac := format_mac(mac)) != mac:
        # The DHCP discovery path did not format the MAC address
        # so we need to update the config entry if it's different
        hass.config_entries.async_update_entry(entry, unique_id=formatted_mac)

    api = Yeti(entry.data[CONF_HOST], async_get_clientsession(hass))
    try:
        await api.init_connect()
    except exceptions.ConnectError as ex:
        raise ConfigEntryNotReady(f"Failed to connect to device: {ex}") from ex

    coordinator = GoalZeroDataUpdateCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
