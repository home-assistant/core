"""Base entity for the Daikin Onecta integration."""

from typing import override

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice


class DaikinOnectaEntity(CoordinatorEntity[OnectaDataUpdateCoordinator]):
    """Base entity for a Daikin gateway device."""

    def __init__(
        self,
        coordinator: OnectaDataUpdateCoordinator,
        device: DaikinOnectaDevice,
    ) -> None:
        """Initialize the entity with its coordinator and gateway device."""
        super().__init__(coordinator)
        self._device = device

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return the gateway device registry information."""
        gateway = self._device.device
        connections = set()
        if gateway.mac_address:
            connections.add((CONNECTION_NETWORK_MAC, gateway.mac_address))

        info = DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            connections=connections,
            manufacturer="Daikin",
            model_id=gateway.device_model,
            name=self._device.name,
        )
        if (embedded_id := gateway.gateway_embedded_id) is not None and (
            management_point := gateway.management_point(embedded_id)
        ) is not None:
            if management_point.model is not None:
                info["model"] = management_point.model
            if management_point.serial is not None:
                info["serial_number"] = management_point.serial
            if management_point.version is not None:
                info["sw_version"] = management_point.version
        return info

    def _async_update_device_registry(self) -> None:
        """Refresh device registry metadata after a coordinator update."""
        dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.coordinator.config_entry.entry_id,
            **self.device_info,
        )
