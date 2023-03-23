"""Sensor for RymPro meters."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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


@dataclass
class RymProSensorDescription(SensorEntityDescription):
    """Class describing rympro sensor entities."""

    sensor: MeterSensor | None = None


SENSOR_DESCRIPTIONS: tuple[RymProSensorDescription, ...] = (
    RymProSensorDescription(
        key="total_consumption",
        sensor=MeterSensor.TOTAL_CONSUMPTION,
        name="Total consumption",
    ),
    RymProSensorDescription(
        key="monthly_forecast",
        sensor=MeterSensor.FORECAST,
        name="Monthly forecast",
    ),
    RymProSensorDescription(
        key="consumption_today",
        sensor=MeterSensor.DAILY_CONSUMPTION,
        name="Consumption today",
    ),
    RymProSensorDescription(
        key="consumption_this_month",
        sensor=MeterSensor.MONTHLY_CONSUMPTION,
        name="Consumption this month",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    coordinator: RymProDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        RymProSensor(coordinator, meter_id, description, config_entry.entry_id)
        for meter_id, meter in coordinator.data.items()
        for description in SENSOR_DESCRIPTIONS
    )


class RymProSensor(CoordinatorEntity[RymProDataUpdateCoordinator], SensorEntity):
    """Sensor for RymPro meters."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_suggested_display_precision = 3
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: RymProDataUpdateCoordinator,
        meter_id: int,
        description: RymProSensorDescription,
        entry_id: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._meter_id = meter_id
        assert description.sensor
        self._sensor = description.sensor
        unique_id = f"{entry_id}_{meter_id}"
        self._attr_unique_id = f"{unique_id}_{description.key}"
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
