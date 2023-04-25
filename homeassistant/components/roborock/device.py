"""Support for Roborock device base class."""

from typing import Any

from roborock.containers import Status
from roborock.typing import RoborockCommand

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RoborockDataUpdateCoordinator
from .const import DOMAIN
from .models import RoborockHassDeviceInfo


class RoborockCoordinatedEntity(CoordinatorEntity[RoborockDataUpdateCoordinator]):
    """Representation of a base a coordinated Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id: str,
        device_info: RoborockHassDeviceInfo,
        coordinator: RoborockDataUpdateCoordinator,
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._device_name = device_info.device.name
        self._device_id = device_info.device.duid
        self._device_model = device_info.product.model
        self._fw_version = device_info.device.fv

    @property
    def _device_status(self) -> Status:
        """Return the status of the device."""
        data = self.coordinator.data
        if data:
            device_data = data.get(self._device_id)
            if device_data:
                status = device_data.status
                if status:
                    return status
        return Status({})

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            name=self._device_name,
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Roborock",
            model=self._device_model,
            sw_version=self._fw_version,
        )

    async def send(
        self, command: RoborockCommand, params: dict[str, Any] | list[Any] | None = None
    ) -> dict:
        """Send a command to a vacuum cleaner."""
        response = await self.coordinator.api.send_command(
            self._device_id, command, params
        )
        await self.coordinator.async_request_refresh()
        return response
