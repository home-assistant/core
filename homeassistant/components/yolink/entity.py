"""Support for YoLink Device."""
from __future__ import annotations

from abc import abstractmethod

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
    ) -> None:
        """Init YoLink Entity."""
        super().__init__(coordinator)

    @property
    def device_id(self) -> str:
        """Return the device id of the YoLink device."""
        return self.coordinator.device.device_id

    async def async_added_to_hass(self) -> None:
        """Update state."""
        await super().async_added_to_hass()
        return self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update state."""
        data = self.coordinator.data
        if data is not None:
            self.update_entity_state(data)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info for HA."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device.device_id)},
            manufacturer=MANUFACTURER,
            model=self.coordinator.device.device_type,
            name=self.coordinator.device.device_name,
        )

    @callback
    @abstractmethod
    def update_entity_state(self, state: dict) -> None:
        """Parse and update entity state, should be overridden."""
