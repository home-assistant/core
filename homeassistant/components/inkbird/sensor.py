"""Support for inkbird ble sensors."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import InkbirdDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the INKBIRD BLE sensors."""
    coordinator: PassiveBluetoothDataUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    entry.async_on_unload(
        coordinator.async_add_entities_listener(
            InkbirdBluetoothSensorEntity, async_add_entities
        )
    )


class InkbirdBluetoothSensorEntity(
    PassiveBluetoothCoordinatorEntity[InkbirdDataUpdateCoordinator], SensorEntity
):
    """Representation of a govee ble sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the native value."""
        return self.coordinator.entity_data.get(self.entity_key)
