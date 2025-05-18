"""The mapping of a Bresser Entity."""

from __future__ import annotations

from aioccl import CCLDevice, CCLSensor

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BresserCoordinator


class BresserEntity(CoordinatorEntity, Entity):
    """Representation of a Bresser Entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        internal: CCLSensor,
        coordinator: BresserCoordinator,
    ) -> None:
        """Initialize a Bresser Entity."""
        super().__init__(coordinator)
        self._internal = internal
        self._device: CCLDevice = coordinator.device

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

    @property
    def available(self) -> bool:
        """Return the availability."""
        return self._internal.value is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
