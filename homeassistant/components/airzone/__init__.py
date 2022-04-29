"""The Airzone integration."""
from __future__ import annotations

import logging
from typing import Any

from aioairzone.const import (
    AZD_ID,
    AZD_MAC,
    AZD_NAME,
    AZD_SYSTEM,
    AZD_THERMOSTAT_FW,
    AZD_THERMOSTAT_MODEL,
    AZD_WEBSERVER,
    AZD_ZONES,
    DEFAULT_SYSTEM_ID,
)
from aioairzone.localapi import AirzoneLocalApi, ConnectionOptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_ID, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    aiohttp_client,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AirzoneUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


class AirzoneEntity(CoordinatorEntity[AirzoneUpdateCoordinator]):
    """Define an Airzone entity."""

    def get_airzone_value(self, key) -> Any:
        """Return Airzone entity value by key."""
        raise NotImplementedError()


class AirzoneZoneEntity(AirzoneEntity):
    """Define an Airzone Zone entity."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        entry: ConfigEntry,
        system_zone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.system_id = zone_data[AZD_SYSTEM]
        self.system_zone_id = system_zone_id
        self.zone_id = zone_data[AZD_ID]

        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{system_zone_id}")},
            "manufacturer": MANUFACTURER,
            "model": self.get_airzone_value(AZD_THERMOSTAT_MODEL),
            "name": f"Airzone [{system_zone_id}] {zone_data[AZD_NAME]}",
            "sw_version": self.get_airzone_value(AZD_THERMOSTAT_FW),
        }
        self._attr_unique_id = (
            entry.entry_id if entry.unique_id is None else entry.unique_id
        )

    def get_airzone_value(self, key) -> Any:
        """Return zone value by key."""
        value = None
        if self.system_zone_id in self.coordinator.data[AZD_ZONES]:
            zone = self.coordinator.data[AZD_ZONES][self.system_zone_id]
            if key in zone:
                value = zone[key]
        return value


async def _async_migrate_unique_ids(
    hass: HomeAssistant,
    entry: ConfigEntry,
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
            new_unique_id = f"{unique_id}{entity_unique_id[len(entry_id):]}"
            _LOGGER.info(
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
