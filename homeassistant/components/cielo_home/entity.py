"""Base entity for Cielo integration."""

from __future__ import annotations

from typing import Any

from cieloconnectapi.model import CieloDevice

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CieloDataUpdateCoordinator


class CieloBaseEntity(CoordinatorEntity[CieloDataUpdateCoordinator]):
    """Representation of a Cielo Base Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CieloDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initiate Cielo Base Entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._client = coordinator.client
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})

    @property
    def client(self) -> Any:
        """Return the API client bound to this entity's current device."""
        if self._client and self.device_data:
            self._client.device_data = self.device_data
        return self._client

    @property
    def device_data(self) -> CieloDevice | None:
        """Return the device data from the coordinator."""
        return self.coordinator.data.parsed.get(self._device_id)


class CieloDeviceBaseEntity(CieloBaseEntity):
    """Representation of a Cielo Device."""

    def __init__(
        self,
        coordinator: CieloDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the device entity."""
        super().__init__(coordinator, device_id)

        device = coordinator.data.parsed.get(device_id)

        # If device data is present, populate full device info
        if device:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, device.id)},
                name=device.name,
                connections={(CONNECTION_NETWORK_MAC, device.mac_address)},
                manufacturer="Cielo",
                configuration_url="https://home.cielowigle.com/",
                suggested_area=device.name,
            )
