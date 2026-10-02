"""The Airzone integration."""

import logging
from typing import Any

from aioairzone.const import (
    AZD_FIRMWARE,
    AZD_FULL_NAME,
    AZD_HOT_WATER,
    AZD_ID,
    AZD_MAC,
    AZD_MODEL,
    AZD_NAME,
    AZD_SYSTEMS,
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

    @callback
    def _async_register_devices() -> None:
        """Register the WebServer, System, and DHW via_device parents.

        The WebServer, Systems, and DHW can appear on later coordinator
        updates, so this runs on every update (before the platform
        listeners) to keep the via_device parents registered before their
        child entities are added.
        """
        ws_device_id: str | None = None
        ws_data: dict[str, Any] | None = coordinator.data.get(AZD_WEBSERVER)
        if ws_data is not None:
            mac = ws_data.get(AZD_MAC, "")

            ws_device = device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                connections={(dr.CONNECTION_NETWORK_MAC, mac)},
                identifiers={(DOMAIN, f"{entry.entry_id}_ws")},
                manufacturer=MANUFACTURER,
                model=ws_data.get(AZD_MODEL),
                name=ws_data.get(AZD_FULL_NAME),
                sw_version=ws_data.get(AZD_FIRMWARE),
            )
            ws_device_id = ws_device.id

        for system_data in coordinator.data.get(AZD_SYSTEMS, {}).values():
            system_id = system_data[AZD_ID]
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, f"{entry.entry_id}_{system_id}")},
                manufacturer=MANUFACTURER,
                model=system_data.get(AZD_MODEL),
                name=f"System {system_id}",
                sw_version=system_data.get(AZD_FIRMWARE),
                via_device_id=ws_device_id,
            )

        dhw_data: dict[str, Any] | None = coordinator.data.get(AZD_HOT_WATER)
        if dhw_data is not None:
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, f"{entry.entry_id}_dhw")},
                manufacturer=MANUFACTURER,
                model="DHW",
                name=dhw_data.get(AZD_NAME),
                via_device_id=ws_device_id,
            )

    # Register the parents before forwarding platforms, and keep them registered
    # as new devices appear so child entities can resolve their via_device_id.
    _async_register_devices()
    entry.async_on_unload(coordinator.async_add_listener(_async_register_devices))

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
