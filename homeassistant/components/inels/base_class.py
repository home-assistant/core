"""Base class for Inels components."""
from __future__ import annotations

from inelsmqtt.devices import Device

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import InelsDeviceUpdateCoordinator


class InelsBaseEntity(CoordinatorEntity[InelsDeviceUpdateCoordinator]):
    """Base Inels device."""

    def __init__(
        self,
        device_coordinator: InelsDeviceUpdateCoordinator,
    ) -> None:
        """Init base entity."""
        super().__init__(device_coordinator)

        self._device: Device = device_coordinator.device
        self._device_id = self._device.unique_id
        self._attr_name = self._device.title

        self._parent_id = self._device.parent_id

        self._attr_unique_id = f"{self._parent_id}-{self._device_id}"

    @callback
    def _refresh(self) -> None:
        """Refresh device data."""
        self.hass.async_add_executor_job(self._device.get_value)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updted data from the coordinator."""
        self._refresh()
        super()._handle_coordinator_update()

    @property
    def should_poll(self) -> bool:
        """Need to poll. Coordinator notifies entity of updates."""
        return True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        info = self._device.info()
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.unique_id)},
            manufacturer=info.manufacturer,
            model=info.model_number,
            name=self._device.title,
            sw_version=info.sw_version,
            via_device=(DOMAIN, self._parent_id),
        )

    @property
    def available(self) -> bool:
        """Return if entity si available."""
        return self._device.is_available and super().available
