"""The Airzone integration."""

from __future__ import annotations

import logging
from typing import Any

from aioairzone.const import (
    AZD_FIRMWARE,
    AZD_FULL_NAME,
    AZD_MAC,
    AZD_MODEL,
    AZD_WEBSERVER,
    DEFAULT_SYSTEM_ID,
)
from aioairzone.localapi import AirzoneLocalApi, ConnectionOptions

from homeassistant.const import CONF_HOST, CONF_ID, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    aiohttp_client,
    device_registry as dr,
    entity_registry as er,
)

from .const import DOMAIN, MANUFACTURER
from .coordinator import AirzoneConfigEntry, AirzoneUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]

_LOGGER = logging.getLogger(__name__)


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
        entry.data[CONF_ID],
    )

    airzone = AirzoneLocalApi(aiohttp_client.async_get_clientsession(hass), options)
    coordinator = AirzoneUpdateCoordinator(hass, entry, airzone)
    await coordinator.async_config_entry_first_refresh()
    await _async_migrate_unique_ids(hass, entry, coordinator)

    entry.runtime_data = coordinator

    device_registry = dr.async_get(hass)

    ws_data: dict[str, Any] | None = coordinator.data.get(AZD_WEBSERVER)
    if ws_data is not None:
        mac = ws_data.get(AZD_MAC, "")

        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            identifiers={(DOMAIN, f"{entry.entry_id}_ws")},
            manufacturer=MANUFACTURER,
            model=ws_data.get(AZD_MODEL),
            name=ws_data.get(AZD_FULL_NAME),
            sw_version=ws_data.get(AZD_FIRMWARE),
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirzoneConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: AirzoneConfigEntry) -> bool:
    """Migrate an old entry."""
    if entry.version == 1 and entry.minor_version < 2:
        # Add missing CONF_ID
        system_id = entry.data.get(CONF_ID, DEFAULT_SYSTEM_ID)
        new_data = entry.data.copy()
        new_data[CONF_ID] = system_id
        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            minor_version=2,
        )

    _LOGGER.info(
        "Migration to configuration version %s.%s successful",
        entry.version,
        entry.minor_version,
    )

    return True
