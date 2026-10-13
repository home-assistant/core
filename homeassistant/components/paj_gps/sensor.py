"""Platform for PAJ GPS sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import override

from pajgps_api.models.sensordata import SensorData
from pajgps_api.models.trackpoint import TrackPoint

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PajGpsConfigEntry
from .coordinator import Device, PajGpsCoordinator
from .entity import PajGpsEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PajGpsSensorEntityDescription(SensorEntityDescription):
    """Describes a PAJ GPS sensor entity."""

    trackpoint_value_fn: Callable[[TrackPoint], int | None] | None = None
    sensor_data_value_fn: Callable[[SensorData], int | None] | None = None
    supported_fn: Callable[[Device], bool] = field(default=lambda _: True)


SENSOR_DESCRIPTIONS: tuple[PajGpsSensorEntityDescription, ...] = (
    PajGpsSensorEntityDescription(
        key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        trackpoint_value_fn=lambda tp: tp.speed,
    ),
    PajGpsSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        trackpoint_value_fn=lambda tp: tp.battery_level,
        supported_fn=lambda device: device.has_battery,
    ),
    PajGpsSensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        sensor_data_value_fn=lambda data: data.volt,
        supported_fn=lambda device: device.has_voltage_sensor,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PajGpsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PAJ GPS sensor entities from a config entry."""
    coordinator = config_entry.runtime_data

    known_device_ids: set[int] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add entities for any device IDs not yet tracked."""
        current_ids = set(coordinator.data.devices.keys())
        new_ids = current_ids - known_device_ids
        if new_ids:
            sorted_new_ids = sorted(new_ids)
            async_add_entities(
                PajGpsSensor(coordinator, device_id, description)
                for device_id in sorted_new_ids
                for description in SENSOR_DESCRIPTIONS
                if description.supported_fn(coordinator.data.devices[device_id])
            )
            known_device_ids.update(sorted_new_ids)

    _async_add_new_devices()

    config_entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class PajGpsSensor(PajGpsEntity, SensorEntity):
    """Sensor entity that reads data from the coordinator snapshot."""

    entity_description: PajGpsSensorEntityDescription

    def __init__(
        self,
        coordinator: PajGpsCoordinator,
        device_id: int,
        description: PajGpsSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.user_id}_{device_id}_{description.key}"

    @property
    @override
    def native_value(self) -> int | None:
        """Return the sensor value from the latest coordinator snapshot."""
        if (
            trackpoint_value_fn := self.entity_description.trackpoint_value_fn
        ) is not None:
            tp = self.coordinator.data.positions.get(self._device_id)
            if tp is None:
                return None
            return trackpoint_value_fn(tp)

        if (
            sensor_data_value_fn := self.entity_description.sensor_data_value_fn
        ) is None:
            return None

        sensor_data = self.coordinator.data.sensor_data.get(self._device_id)
        if sensor_data is None:
            return None
        return sensor_data_value_fn(sensor_data)

    @property
    @override
    def available(self) -> bool:
        """Return if the sensor is available."""
        if self.entity_description.key != "voltage":
            return super().available

        return (
            super().available and self._device_id in self.coordinator.data.sensor_data
        )
