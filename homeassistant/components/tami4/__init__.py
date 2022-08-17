"""The Tami4Edge integration."""
from __future__ import annotations

from Tami4EdgeAPI import Tami4EdgeAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import CONF_REFRESH_TOKEN, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


class Tami4EdgeBaseEntity(Entity):
    """Base class for Tami4Edge entities."""

    def __init__(
        self, edge: Tami4EdgeAPI, entity_description: EntityDescription
    ) -> None:
        """Initialize the Tami4Edge."""
        self._state = None
        self._edge = edge
        self._name = f"{edge.device.name}"
        self._device_id = edge.device.psn
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._device_id}_{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, edge.device.psn)},
            manufacturer="Stratuss",
            name=edge.device.name,
            model="Tami4",
            sw_version=edge.device.device_firmware,
            suggested_area="Kitchen",
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up edge from a config entry."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    refresh_token = entry.data.get(CONF_REFRESH_TOKEN)

    try:
        edge = await hass.async_add_executor_job(Tami4EdgeAPI, refresh_token)
    except Exception as ex:
        raise PlatformNotReady(f"CError connecting to API : {ex}") from ex

    hass.data[DOMAIN][entry.entry_id] = edge

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
