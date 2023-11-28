"""Binary sensor for Wyoming."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WyomingSatelliteEntity
from .satellite import SatelliteDevice

if TYPE_CHECKING:
    from .models import DomainDataItem


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    domain_data: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def async_add_device(device: SatelliteDevice) -> None:
        """Add device."""
        async_add_entities([WyomingSatelliteAssistInProgress(device)])

    domain_data.satellite_devices.async_add_new_device_listener(async_add_device)

    async_add_entities(
        [
            WyomingSatelliteAssistInProgress(device)
            for device in domain_data.satellite_devices
        ]
    )


class WyomingSatelliteAssistInProgress(WyomingSatelliteEntity, BinarySensorEntity):
    """Entity to represent Assist is in progress for satellite."""

    entity_description = BinarySensorEntityDescription(
        key="assist_in_progress",
        translation_key="assist_in_progress",
    )
    _attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(self._device.async_listen_update(self._is_active_changed))

    @callback
    def _is_active_changed(self, device: SatelliteDevice) -> None:
        """Call when active state changed."""
        self._attr_is_on = self._device.is_active
        self.async_write_ha_state()
