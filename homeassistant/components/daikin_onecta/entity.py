"""Base entity for the Daikin Onecta integration."""

from typing import Never, override

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    ChildDeviceInfo,
    DeviceInfo,
)
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

    def _raise_service_validation_error(self, translation_key: str) -> Never:
        """Raise a translated error for an unavailable device control."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"device": self._device.name},
        )

    def _raise_command_failed(self, translation_key: str) -> Never:
        """Raise a translated error when Daikin rejects a command."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"device": self._device.name},
        )

    @property
    @override
    def device_info(self) -> DeviceInfo | ChildDeviceInfo:
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
