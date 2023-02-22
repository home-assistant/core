"""Support for Roborock device base class."""

from roborock.containers import Status
from roborock.typing import RoborockCommand, RoborockDeviceInfo

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RoborockDataUpdateCoordinator
from .const import DOMAIN


class RoborockCoordinatedEntity(CoordinatorEntity[RoborockDataUpdateCoordinator]):
    """Representation of a base a coordinated Roborock Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device_info: RoborockDeviceInfo,
        coordinator: RoborockDataUpdateCoordinator,
        unique_id: str | None = None,
    ) -> None:
        """Initialize the coordinated Roborock Device."""
        super().__init__(coordinator)
        self._device_name = device_info.device.name
        self._attr_unique_id = unique_id
        self._device_id = str(device_info.device.duid)
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

    async def send(self, command: RoborockCommand, params=None):
        """Send a command to a vacuum cleaner."""
        return await self.coordinator.api.send_command(self._device_id, command, params)
