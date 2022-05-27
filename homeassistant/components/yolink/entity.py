"""Support for YoLink Device."""
from __future__ import annotations

from abc import abstractmethod

from yolink.device import YoLinkDevice

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import YoLinkCoordinator


class YoLinkEntity(CoordinatorEntity[YoLinkCoordinator]):
    """YoLink Device Basic Entity."""

    def __init__(
        self,
        coordinator: YoLinkCoordinator,
        device_info: YoLinkDevice,
    ) -> None:
        """Init YoLink Entity."""
        super().__init__(coordinator)
        self.device = device_info

    @property
    def device_id(self) -> str:
        """Return the device id of the YoLink device."""
        return self.device.device_id

    async def async_added_to_hass(self) -> None:
        """Update state."""
        return self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update state."""
        data = self.coordinator.data.get(self.device.device_id)
        if data is not None:
            self.update_entity_state(data)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info for HA."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id)},
            manufacturer=MANUFACTURER,
            model=self.device.device_type,
            name=self.device.device_name,
        )

    @callback
    @abstractmethod
    def update_entity_state(self, state: dict) -> None:
        """Parse and update entity state, should be overridden."""
