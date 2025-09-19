"""Base entity definition for Nintendo Parental."""

from __future__ import annotations

from pynintendoparental import Device

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NintendoUpdateCoordinator


class NintendoDevice(CoordinatorEntity[NintendoUpdateCoordinator]):
    """Represent a Nintendo Switch."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: NintendoUpdateCoordinator, device: Device, key: str
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = f"{device.device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            manufacturer="Nintendo",
            name=device.name,
            sw_version=device.extra["firmwareVersion"]["displayedVersion"],
        )

    async def async_added_to_hass(self) -> None:
        """When entity is loaded."""
        await super().async_added_to_hass()
        self._device.add_device_callback(self.async_write_ha_state)

    async def async_removed_from_registry(self) -> None:
        """When entity is removed."""
        self._device.remove_device_callback(self.async_write_ha_state)
