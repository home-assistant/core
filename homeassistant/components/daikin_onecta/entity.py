"""Base entities for the Daikin Onecta integration."""

from collections.abc import Awaitable, Callable
from typing import Never, override

from daikin_onecta.client import OnectaClient

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice


def _add_management_point_metadata(
    info: DeviceInfo, device: DaikinOnectaDevice, embedded_id: str
) -> None:
    """Add management-point metadata to a device-info object."""
    if (management_point := device.management_point(embedded_id)) is None:
        return
    if management_point.model is not None:
        info["model"] = management_point.model
    if management_point.serial is not None:
        info["serial_number"] = management_point.serial
    if management_point.version is not None:
        info["sw_version"] = management_point.version


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
            gateway.management_point(embedded_id) is not None
        ):
            _add_management_point_metadata(info, self._device, embedded_id)
        return info


class DaikinEntity(DaikinOnectaEntity):
    """Compatibility base for entities backed by a Daikin gateway."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str | None = None,
        management_point_type: str | None = None,
    ) -> None:
        """Initialize shared coordinator and device state."""
        super().__init__(coordinator, device)
        self._embedded_id = embedded_id

    @property
    @override
    def available(self) -> bool:
        """Return whether the coordinator and Daikin device are available."""
        return super().available and self._device.available

    async def _async_execute_command(
        self,
        command: Callable[[OnectaClient], Awaitable[None]],
        translation_key: str,
    ) -> None:
        """Execute a cloud command or raise a translated Home Assistant error."""
        if not await self.coordinator.api.async_execute_command(command):
            self._raise_command_failed(translation_key)

    def _raise_command_failed(self, translation_key: str) -> Never:
        """Raise a translated command error for this device."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"device": self._device.name},
        )


class DaikinManagementPointEntity(DaikinEntity):
    """Base entity backed by a Daikin management point."""

    _embedded_id: str

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str,
        management_point_type: str | None = None,
    ) -> None:
        """Initialize a management-point entity."""
        super().__init__(device, coordinator, embedded_id, management_point_type)
        self._embedded_id = embedded_id
