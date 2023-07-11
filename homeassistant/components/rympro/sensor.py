"""Sensor for RymPro meters."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RymProDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    coordinator: RymProDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        RymProSensor(coordinator, meter_id, meter["read"], config_entry.entry_id)
        for meter_id, meter in coordinator.data.items()
    )


class RymProSensor(CoordinatorEntity[RymProDataUpdateCoordinator], SensorEntity):
    """Sensor for RymPro meters."""

    _attr_has_entity_name = True
    _attr_translation_key = "total_consumption"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: RymProDataUpdateCoordinator,
        meter_id: int,
        last_read: int,
        entry_id: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._meter_id = meter_id
        unique_id = f"{entry_id}_{meter_id}"
        self._attr_unique_id = f"{unique_id}_total_consumption"
        self._attr_extra_state_attributes = {"meter_id": str(meter_id)}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Read Your Meter Pro",
            name=f"Meter {meter_id}",
        )
        self._attr_native_value = last_read

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.data[self._meter_id]["read"]
