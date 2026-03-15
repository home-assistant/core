"""Base entity for Cielo integration."""

from __future__ import annotations

from cieloconnectapi.device import CieloDeviceAPI
from cieloconnectapi.model import CieloDevice

from homeassistant.exceptions import HomeAssistantError
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
        self._client = coordinator.client
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})
        self._device_api: CieloDeviceAPI | None = None

    @property
    def client(self) -> CieloDeviceAPI:
        """Return a per-device API wrapper."""
        dev = self.device_data
        if dev is None:
            raise HomeAssistantError(
                f"Cielo device {self._device_id} data not available"
            )

        if self._device_api is None:
            self._device_api = CieloDeviceAPI(self._client, dev)
        else:
            self._device_api.device_data = dev

        return self._device_api

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


class CieloDeviceBaseEntity(CieloBaseEntity):
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
