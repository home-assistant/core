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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RymProDataUpdateCoordinator


@dataclass(kw_only=True, frozen=True)
class RymProSensorEntityDescription(SensorEntityDescription):
    """Class describing RymPro sensor entities."""

    value_key: str


SENSOR_DESCRIPTIONS: tuple[RymProSensorEntityDescription, ...] = (
    RymProSensorEntityDescription(
        key="total_consumption",
        translation_key="total_consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_key="read",
    ),
    RymProSensorEntityDescription(
        key="monthly_consumption",
        translation_key="monthly_consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_key="monthly_consumption",
    ),
    RymProSensorEntityDescription(
        key="daily_consumption",
        translation_key="daily_consumption",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_key="daily_consumption",
    ),
    RymProSensorEntityDescription(
        key="monthly_forecast",
        translation_key="monthly_forecast",
        suggested_display_precision=3,
        value_key="consumption_forecast",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
    entity_description: RymProSensorEntityDescription

    def __init__(
        self,
        coordinator: RymProDataUpdateCoordinator,
        meter_id: int,
        description: RymProSensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._meter_id = meter_id
        unique_id = f"{entry_id}_{meter_id}"
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self._attr_extra_state_attributes = {"meter_id": str(meter_id)}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Read Your Meter Pro",
            name=f"Meter {meter_id}",
        )
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.data[self._meter_id][self.entity_description.value_key]
