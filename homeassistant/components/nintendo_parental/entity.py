"""Base entity definition for Nintendo Parental."""

from __future__ import annotations

from pynintendoparental import Device

import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NintendoUpdateCoordinator


class NintendoDevice(CoordinatorEntity):
    """Represent a Nintendo Switch."""

    def __init__(
        self, coordinator: NintendoUpdateCoordinator, device: Device, entity_id: str
    ) -> None:
        """Initialize."""
        super().__init__(coordinator=coordinator)
        self._device = device
        self._attr_unique_id = f"{device.device_id}_{entity_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            manufacturer="Nintendo",
            name=device.name,
            entry_type=dr.DeviceEntryType.SERVICE,
            sw_version=device.extra["device"]["firmwareVersion"]["displayedVersion"],
        )

    async def async_added_to_hass(self) -> None:
        """When entity is loaded."""
        await super().async_added_to_hass()
        self._device.add_device_callback(self.async_write_ha_state)
