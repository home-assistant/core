"""Base class for Ring entity."""
from typing import TypeVar

from ring_doorbell.generic import RingGeneric

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import (
    RingDataCoordinator,
    RingDeviceData,
    RingNotificationsCoordinator,
)

_RingCoordinatorT = TypeVar(
    "_RingCoordinatorT",
    bound=(RingDataCoordinator | RingNotificationsCoordinator),
)


class RingEntity(CoordinatorEntity[_RingCoordinatorT]):
    """Base implementation for Ring device."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        device: RingGeneric,
        coordinator: _RingCoordinatorT,
    ) -> None:
        """Initialize a sensor for Ring device."""
        super().__init__(coordinator, context=device.id)
        self._device = device
        self._attr_extra_state_attributes = {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},  # device_id is the mac
            manufacturer="Ring",
            model=device.model,
            name=device.name,
        )

    def _get_coordinator_device_data(self) -> RingDeviceData | None:
        if (data := self.coordinator.data) and (
            device_data := data.get(self._device.id)
        ):
            return device_data
        return None

    def _get_coordinator_device(self) -> RingGeneric | None:
        if (device_data := self._get_coordinator_device_data()) and (
            device := device_data.device
        ):
            return device
        return None

    def _get_coordinator_history(self) -> list | None:
        if (device_data := self._get_coordinator_device_data()) and (
            history := device_data.history
        ):
            return history
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        if device := self._get_coordinator_device():
            self._device = device
        super()._handle_coordinator_update()
