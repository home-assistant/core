"""Base entity for the ISEO Argo BLE Lock integration."""

from typing import cast

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo

from .const import DOMAIN
from .coordinator import IseoCoordinator


class IseoEntity(PassiveBluetoothCoordinatorEntity[IseoCoordinator]):
    """Base class for ISEO Argo BLE entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IseoCoordinator) -> None:
        """Initialize an ISEO entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._fw_version_set = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cast(str, entry.unique_id))},
            connections={(CONNECTION_BLUETOOTH, entry.data[CONF_ADDRESS])},
            manufacturer="ISEO",
            model="X1R Smart",
            model_id="X1R",
        )

    @callback
    def _async_update_firmware_version(self) -> None:
        """Store the firmware version reported by the lock, once."""
        state = self.coordinator.data
        if self._fw_version_set or state is None or not state.firmware_info:
            return
        if (device := self.device_entry) is None:
            return

        # The lock reports the version prefixed, e.g. "FW:  1.2.3"; fall back to
        # the raw string if the prefix is missing.
        fw_version = (
            state.firmware_info.removeprefix("FW:").strip()
            or state.firmware_info.strip()
        )
        dr.async_get(self.hass).async_update_device(device.id, sw_version=fw_version)
        self._fw_version_set = True
