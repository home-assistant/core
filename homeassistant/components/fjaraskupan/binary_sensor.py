"""Support for sensors."""
from __future__ import annotations

from fjaraskupan import Device, State

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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

    def _constructor(devicestate: DeviceState):
        return [
            GreaseFilterSensor(
                devicestate.coordinator, devicestate.device, devicestate.device_info
            ),
            CarbonFilterSensor(
                devicestate.coordinator, devicestate.device, devicestate.device_info
            ),
        ]

    async_setup_entry_platform(hass, config_entry, async_add_entities, _constructor)


class GreaseFilterSensor(CoordinatorEntity[State], BinarySensorEntity):
    """Grease filter sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[State],
        device: Device,
        device_info: DeviceInfo,
    ) -> None:
        """Init sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device.address}-grease-filter"
        self._attr_device_info = device_info
        self._attr_name = f"{device_info['name']} Grease Filter"
        self._attr_device_class = DEVICE_CLASS_PROBLEM

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if data := self.coordinator.data:
            return data.grease_filter_full
        return None


class CarbonFilterSensor(CoordinatorEntity[State], BinarySensorEntity):
    """Grease filter sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[State],
        device: Device,
        device_info: DeviceInfo,
    ) -> None:
        """Init sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{device.address}-carbon-filter"
        self._attr_device_info = device_info
        self._attr_name = f"{device_info['name']} Carbon Filter"
        self._attr_device_class = DEVICE_CLASS_PROBLEM

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if data := self.coordinator.data:
            return data.carbon_filter_full
        return None
