"""Sensor platform for the Laifen integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from laifen_ble import LaifenToothbrush

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LaifenConfigEntry
from .entity import LaifenEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LaifenSensorEntityDescription(SensorEntityDescription):
    """Describes a Laifen sensor."""

    value_fn: Callable[[LaifenToothbrush], int | None]


SENSORS: tuple[LaifenSensorEntityDescription, ...] = (
    LaifenSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda toothbrush: (
            toothbrush.state.battery_level if toothbrush.state else None
        ),
    ),
    LaifenSensorEntityDescription(
        key="last_brushing_duration",
        translation_key="last_brushing_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        value_fn=lambda toothbrush: (
            toothbrush.last_session.duration if toothbrush.last_session else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaifenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Laifen sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        LaifenSensor(coordinator, description) for description in SENSORS
    )


class LaifenSensor(LaifenEntity, RestoreSensor):
    """A Laifen sensor that keeps its last value while the toothbrush sleeps."""

    entity_description: LaifenSensorEntityDescription

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last value."""
        await super().async_added_to_hass()
        if (last_sensor_data := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = last_sensor_data.native_value
        self._update_native_value()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the toothbrush."""
        self._update_native_value()
        super()._handle_coordinator_update()

    def _update_native_value(self) -> None:
        """Update the value from the toothbrush."""
        if (value := self.entity_description.value_fn(self.toothbrush)) is not None:
            self._attr_native_value = value

    @property
    @override
    def available(self) -> bool:
        """Return whether the sensor is available."""
        return super().available and (
            self.toothbrush.connected or self.native_value is not None
        )
