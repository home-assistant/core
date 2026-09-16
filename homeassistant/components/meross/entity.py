"""Base entity for Meross Bluetooth."""

from __future__ import annotations

from typing import Any

from meross_ble import MODEL_FRIENDLY_NAME

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, LOGGER, MANUFACTURER
from .coordinator import MerossBLEDataUpdateCoordinator


class MerossBLEEntity(
    PassiveBluetoothCoordinatorEntity[MerossBLEDataUpdateCoordinator]
):
    """Base Meross BLE entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MerossBLEDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._address = coordinator.ble_device.address
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_BLUETOOTH, self._address)},
            identifiers={(DOMAIN, coordinator.base_unique_id)},
            manufacturer=MANUFACTURER,
            model=MODEL_FRIENDLY_NAME.get(coordinator.model, coordinator.model.value),
            name=coordinator.device_name,
        )
        self._last_logged_available: bool | None = None
        self._last_logged_value: Any = object()

    @property
    def parsed_data(self) -> dict[str, Any]:
        return self.coordinator.device.parsed_data

    def _entity_log_key(self) -> str:
        desc = getattr(self, "entity_description", None)
        if desc is not None and getattr(desc, "key", None):
            return str(desc.key)
        sensor = getattr(self, "_sensor", None)
        if sensor:
            return str(sensor)
        return type(self).__name__

    def _entity_log_value(self) -> Any:
        native = getattr(type(self), "native_value", None)
        if isinstance(native, property):
            return self.native_value
        is_on = getattr(type(self), "is_on", None)
        if isinstance(is_on, property):
            return self.is_on
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write HA state; INFO only when availability changes, DEBUG for value."""
        available = self.available
        value = self._entity_log_value()
        if available != self._last_logged_available:
            LOGGER.info(
                "%s: %s HA entity %s available=%s value=%r",
                self._address,
                self.coordinator.model.value.upper(),
                self._entity_log_key(),
                available,
                value,
            )
            self._last_logged_available = available
            self._last_logged_value = value
        elif value != self._last_logged_value:
            LOGGER.debug(
                "%s: %s HA entity %s available=%s value=%r",
                self._address,
                self.coordinator.model.value.upper(),
                self._entity_log_key(),
                available,
                value,
            )
            self._last_logged_value = value
        super()._handle_coordinator_update()
