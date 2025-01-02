"""The Knocki integration."""

from __future__ import annotations

from knocki import Event, EventType, KnockiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import KnockiCoordinator

PLATFORMS: list[Platform] = [Platform.EVENT]

type KnockiConfigEntry = ConfigEntry[KnockiCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: KnockiConfigEntry) -> bool:
    """Set up Knocki from a config entry."""
    client = KnockiClient(
        session=async_get_clientsession(hass), token=entry.data[CONF_TOKEN]
    )

    coordinator = KnockiCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(
        client.register_listener(EventType.CREATED, coordinator.add_trigger)
    )

    async def _refresh_coordinator(_: Event) -> None:
        await coordinator.async_refresh()

    entry.async_on_unload(
        client.register_listener(EventType.DELETED, _refresh_coordinator)
    )

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await client.start_websocket()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KnockiConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.client.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
