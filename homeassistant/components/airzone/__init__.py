"""The Airzone integration."""

from __future__ import annotations

import logging
from typing import Any

from aioairzone.const import AZD_MAC, AZD_WEBSERVER, DEFAULT_SYSTEM_ID
from aioairzone.localapi import AirzoneLocalApi, ConnectionOptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_ID, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    aiohttp_client,
    device_registry as dr,
    entity_registry as er,
)

from .coordinator import AirzoneUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.WATER_HEATER,
]

_LOGGER = logging.getLogger(__name__)

type AirzoneConfigEntry = ConfigEntry[AirzoneUpdateCoordinator]


async def _async_migrate_unique_ids(
    hass: HomeAssistant,
    entry: AirzoneConfigEntry,
    coordinator: AirzoneUpdateCoordinator,
) -> None:
    """Migrate entities when the mac address gets discovered."""

    @callback
    def _async_migrator(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
        updates = None

        unique_id = entry.unique_id
        entry_id = entry.entry_id
        entity_unique_id = entity_entry.unique_id

        if entity_unique_id.startswith(entry_id):
            new_unique_id = f"{unique_id}{entity_unique_id.removeprefix(entry_id)}"
            _LOGGER.debug(
                "Migrating unique_id from [%s] to [%s]",
                entity_unique_id,
                new_unique_id,
            )
            updates = {"new_unique_id": new_unique_id}

        return updates

    if (
        entry.unique_id is None
        and AZD_WEBSERVER in coordinator.data
        and AZD_MAC in coordinator.data[AZD_WEBSERVER]
        and (mac := coordinator.data[AZD_WEBSERVER][AZD_MAC]) is not None
    ):
        updates: dict[str, Any] = {
            "unique_id": dr.format_mac(mac),
        }
        hass.config_entries.async_update_entry(entry, **updates)

        await er.async_migrate_entries(hass, entry.entry_id, _async_migrator)


async def async_setup_entry(hass: HomeAssistant, entry: AirzoneConfigEntry) -> bool:
    """Set up Airzone from a config entry."""
    options = ConnectionOptions(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data.get(CONF_ID, DEFAULT_SYSTEM_ID),
    )

    airzone = AirzoneLocalApi(aiohttp_client.async_get_clientsession(hass), options)
    coordinator = AirzoneUpdateCoordinator(hass, airzone)
    await coordinator.async_config_entry_first_refresh()
    await _async_migrate_unique_ids(hass, entry, coordinator)

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirzoneConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
