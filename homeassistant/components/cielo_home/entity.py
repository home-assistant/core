"""Base entity for Cielo integration."""

from __future__ import annotations

from cieloconnectapi.device import CieloDeviceAPI
from cieloconnectapi.model import CieloDevice

from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CieloDataUpdateCoordinator


class CieloBaseEntity(CoordinatorEntity[CieloDataUpdateCoordinator]):
    """Representation of a Cielo base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CieloDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the Cielo base entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self.client = CieloDeviceAPI(
            coordinator.client, coordinator.data.parsed[device_id]
        )

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (dev := self.device_data) is not None:
            self.client.device_data = dev
        super()._handle_coordinator_update()

    @property
    def device_data(self) -> CieloDevice | None:
        """Return the device data from the coordinator."""
        return self.coordinator.data.parsed.get(self._device_id)

    @property
    def available(self) -> bool:
        """Return if the device is available and online."""
        if not (super().available and self._device_id in self.coordinator.data.parsed):
            return False

        dev = self.device_data
        return bool(dev and dev.device_status)


class CieloDeviceEntity(CieloBaseEntity):
    """Representation of a Cielo Device."""

    def __init__(
        self,
        coordinator: CieloDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the device entity."""
        super().__init__(coordinator, device_id)
        self.device_id = device_id

        device = coordinator.data.parsed[device_id]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=device.name,
            connections={(CONNECTION_NETWORK_MAC, format_mac(device.mac_address))},
            manufacturer="Cielo",
            configuration_url="https://home.cielowigle.com/",
            suggested_area=device.name,
        )
