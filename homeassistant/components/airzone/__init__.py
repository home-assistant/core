"""The Airzone integration."""
from __future__ import annotations

from aioairzone.common import ConnectionOptions
from aioairzone.localapi_device import AirzoneLocalApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AirzoneUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


class AirzoneEntity(CoordinatorEntity):
    """Define an Airzone entity."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        entry: ConfigEntry,
        system_zone_id: str,
        zone_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, f"{entry.entry_id, system_zone_id}")},
            "manufacturer": MANUFACTURER,
            "name": f"Airzone [{system_zone_id}] {zone_name}",
        }
        self.system_zone_id = system_zone_id


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Airzone from a config entry."""
    options = ConnectionOptions(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
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
