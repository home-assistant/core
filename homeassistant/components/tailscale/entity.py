"""The Tailscale integration."""

from __future__ import annotations

from tailscale import Device as TailscaleDevice

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class TailscaleEntity(CoordinatorEntity):
    """Defines a Tailscale base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: DataUpdateCoordinator,
        device: TailscaleDevice,
        description: EntityDescription,
    ) -> None:
        """Initialize a Tailscale sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self.device_id = device.device_id
        self._attr_unique_id = f"{device.device_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        device: TailscaleDevice = self.coordinator.data[self.device_id]

        configuration_url = "https://login.tailscale.com/admin/machines/"
        if device.addresses:
            configuration_url += device.addresses[0]

        return DeviceInfo(
            configuration_url=configuration_url,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, device.device_id)},
            manufacturer="Tailscale Inc.",
            model=device.os,
            name=device.name.split(".")[0],
            sw_version=device.client_version,
        )
