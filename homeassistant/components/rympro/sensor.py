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

from .const import DOMAIN, MeterSensor
from .coordinator import RymProDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    coordinator: RymProDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        entity
        for meter_id, meter in coordinator.data.items()
        for entity in (
            RymProSensor(
                coordinator,
                meter_id,
                sensor=MeterSensor.TOTAL_CONSUMPTION,
                name="Total consumption",
                uid_suffix="total_consumption",
                entry_id=config_entry.entry_id,
            ),
            RymProSensor(
                coordinator,
                meter_id,
                sensor=MeterSensor.FORECAST,
                name="Monthly forecast",
                uid_suffix="monthly_forecast",
                entry_id=config_entry.entry_id,
            ),
            RymProSensor(
                coordinator,
                meter_id,
                sensor=MeterSensor.DAILY_CONSUMPTION,
                name="Consumption today",
                uid_suffix="consumption_today",
                entry_id=config_entry.entry_id,
            ),
            RymProSensor(
                coordinator,
                meter_id,
                sensor=MeterSensor.MONTHLY_CONSUMPTION,
                name="Consumption this month",
                uid_suffix="consumption_this_month",
                entry_id=config_entry.entry_id,
            ),
        )
    )


class RymProSensor(CoordinatorEntity[RymProDataUpdateCoordinator], SensorEntity):
    """Sensor for RymPro meters."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_native_precision = 3
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: RymProDataUpdateCoordinator,
        meter_id: int,
        sensor: MeterSensor,
        name: str,
        uid_suffix: str,
        entry_id: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._meter_id = meter_id
        self._sensor = sensor
        self._attr_name = name
        unique_id = f"{entry_id}_{meter_id}"
        self._attr_unique_id = f"{unique_id}_{uid_suffix}"
        self._attr_extra_state_attributes = {"meter_id": str(meter_id)}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Read Your Meter Pro",
            name=f"Meter {meter_id}",
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.add_meter_sensor(self._meter_id, self._sensor)
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.data[self._meter_id].get(self._sensor)
