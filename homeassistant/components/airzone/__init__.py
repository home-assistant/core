"""The Airzone integration."""
from __future__ import annotations

from typing import Any

from aioairzone.const import (
    AZD_ID,
    AZD_NAME,
    AZD_SYSTEM,
    AZD_THERMOSTAT_FW,
    AZD_THERMOSTAT_MODEL,
    AZD_ZONES,
    DEFAULT_SYSTEM_ID,
)
from aioairzone.localapi import AirzoneLocalApi, ConnectionOptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_ID, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AirzoneUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.SENSOR]


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

    def get_airzone_value(self, key) -> Any:
        """Return zone value by key."""
        value = None
        if self.system_zone_id in self.coordinator.data[AZD_ZONES]:
            zone = self.coordinator.data[AZD_ZONES][self.system_zone_id]
            if key in zone:
                value = zone[key]
        return value


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

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
