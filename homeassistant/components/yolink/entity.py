"""Support for YoLink Device."""
from __future__ import annotations

from abc import abstractmethod

from yolink.device import YoLinkDevice

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import YoLinkCoordinator
from .const import DOMAIN, MANUFACTURER


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

    @callback
    def _handle_coordinator_update(self) -> None:
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

    def _async_set_unavailable(self, now) -> None:
        """Set state to UNAVAILABLE."""
        self._attr_available = False

    @callback
    @abstractmethod
    def update_entity_state(self, state: dict) -> None:
        """Parse and update entity state, should be overridden."""
