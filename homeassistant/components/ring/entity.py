"""Base class for Ring entity."""
from typing import Optional, TypeVar

from ring_doorbell.generic import RingGeneric

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import RingDataCoordinator, RingNotificationsCoordinator

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

    def _get_coordinator_device(self) -> Optional[RingGeneric]:
        if (
            self.coordinator.data
            and self._device.id in self.coordinator.data
            and self.coordinator.data[self._device.id].device
        ):
            return self.coordinator.data[self._device.id].device
        return None

    def _get_coordinator_history(self) -> Optional[list]:
        if (
            self.coordinator.data
            and self._device.id in self.coordinator.data
            and self.coordinator.data[self._device.id].history
        ):
            return self.coordinator.data[self._device.id].history
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        if device := self._get_coordinator_device():
            self._device = device
        super()._handle_coordinator_update()
