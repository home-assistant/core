"""The UniFi Access integration."""

from __future__ import annotations

from uiaccessclient import ApiClient, WebsocketClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .coordinator import UniFiAccessDoorCoordinator
from .data import UniFiAccessData

PLATFORMS: list[Platform] = [Platform.LOCK]

type UniFiAccessConfigEntry = ConfigEntry[UniFiAccessData]


async def async_setup_entry(hass: HomeAssistant, entry: UniFiAccessConfigEntry) -> bool:
    """Configure UniFi Access integration."""
    api_client = ApiClient(entry.data.get(CONF_HOST), entry.data.get(CONF_API_TOKEN))
    websocket_client = WebsocketClient(
        entry.data.get(CONF_HOST), entry.data.get(CONF_API_TOKEN)
    )

    door_coordinator = UniFiAccessDoorCoordinator(hass, api_client, websocket_client)
    await door_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = UniFiAccessData(
        api_client=api_client,
        door_coordinator=door_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: UniFiAccessConfigEntry
) -> bool:
    """Unload UniFi Access integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
