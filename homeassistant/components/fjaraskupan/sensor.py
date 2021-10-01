"""Support for sensors."""
from __future__ import annotations

from fjaraskupan import Device, State

from homeassistant.components.sensor import (
    DEVICE_CLASS_SIGNAL_STRENGTH,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DeviceState, async_setup_entry_platform


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors dynamically through discovery."""

    def _constructor(device_state: DeviceState) -> list[Entity]:
        return [
            RssiSensor(
                device_state.coordinator, device_state.device, device_state.device_info
            )
        ]

    async_setup_entry_platform(hass, config_entry, async_add_entities, _constructor)


class RssiSensor(CoordinatorEntity[State], SensorEntity):
    """Sensor device."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[State],
        device: Device,
        device_info: DeviceInfo,
    ) -> None:
        """Init sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device.address}-signal-strength"
        self._attr_device_info = device_info
        self._attr_name = f"{device_info['name']} Signal Strength"
        self._attr_device_class = DEVICE_CLASS_SIGNAL_STRENGTH
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        self._attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        if data := self.coordinator.data:
            return data.rssi
        return None
