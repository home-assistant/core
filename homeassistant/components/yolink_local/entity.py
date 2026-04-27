"""Support for YoLink Device."""

from __future__ import annotations

from abc import abstractmethod

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import YoLinkLocalCoordinator


class YoLinkEntity(CoordinatorEntity[YoLinkLocalCoordinator]):
    """YoLink Device Basic Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: YoLinkLocalCoordinator,
    ) -> None:
        """Init YoLink Entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device.device_id)},
            manufacturer=MANUFACTURER,
            model=self.coordinator.device.device_type,
            model_id=self.coordinator.device.device_model_name,
            name=self.coordinator.device.device_name,
        )

    @property
    def device_id(self) -> str:
        """Return the device id of the YoLink device."""
        return self.coordinator.device.device_id

    @property
    def available(self) -> bool:
        """Returns whether entity is available."""
        return super().available and self.coordinator.is_device_online

    async def async_added_to_hass(self) -> None:
        """Update state."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update state."""
        if (state_data := self.coordinator.data) is not None and len(state_data) > 0:
            self.update_entity_state(state_data)

    @callback
    @abstractmethod
    def update_entity_state(self, state: dict) -> None:
        """Parse and update entity state, should be overridden."""
