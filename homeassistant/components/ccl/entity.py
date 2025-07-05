"""The mapping of a CCL Entity."""

from __future__ import annotations

import time

from aioccl import CCLSensor

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CCLCoordinator


class CCLEntity(CoordinatorEntity[CCLCoordinator]):
    """Representation of a CCL Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        internal: CCLSensor,
        coordinator: CCLCoordinator,
    ) -> None:
        """Initialize a CCL Entity."""
        super().__init__(coordinator)
        self._internal = internal
        self._device = coordinator.device

        if internal.compartment is not None:
            self.device_id = (
                self._device.device_id + "_" + internal.compartment
            ).lower()
            self.device_name = self._device.name + " " + internal.compartment
        else:
            self.device_id = self._device.device_id
            self.device_name = self._device.name

        self._attr_unique_id = f"{self._device.device_id}-{internal.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self.device_id),
            },
            model=self._device.model,
            name=self.device_name,
            manufacturer="CCL Electronics",
            sw_version=self._device.fw_ver,
        )
        self._attr_should_poll = True

    @property
    def available(self) -> bool:
        """Return the availability."""
        return (
            self._internal.value is not None
            and super().available
            and time.monotonic() - self._internal.last_update_time <= 600
        )
