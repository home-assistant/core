"""PEGELONLINE sensor entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aiopegelonline.models import CurrentMeasurement, StationMeasurements

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PegelOnlineConfigEntry, PegelOnlineDataUpdateCoordinator
from .entity import PegelOnlineEntity


@dataclass(frozen=True, kw_only=True)
class PegelOnlineSensorEntityDescription(SensorEntityDescription):
    """PEGELONLINE sensor entity description."""

    measurement_fn: Callable[[StationMeasurements], CurrentMeasurement | None]


SENSORS: tuple[PegelOnlineSensorEntityDescription, ...] = (
    PegelOnlineSensorEntityDescription(
        key="air_temperature",
        translation_key="air_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        measurement_fn=lambda data: data.air_temperature,
    ),
    PegelOnlineSensorEntityDescription(
        key="clearance_height",
        translation_key="clearance_height",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        measurement_fn=lambda data: data.clearance_height,
    ),
    PegelOnlineSensorEntityDescription(
        key="oxygen_level",
        translation_key="oxygen_level",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        measurement_fn=lambda data: data.oxygen_level,
    ),
    PegelOnlineSensorEntityDescription(
        key="ph_value",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PH,
        entity_registry_enabled_default=False,
        measurement_fn=lambda data: data.ph_value,
    ),
    PegelOnlineSensorEntityDescription(
        key="water_speed",
        translation_key="water_speed",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SPEED,
        entity_registry_enabled_default=False,
        measurement_fn=lambda data: data.water_speed,
    ),
    PegelOnlineSensorEntityDescription(
        key="water_flow",
        translation_key="water_flow",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        entity_registry_enabled_default=False,
        measurement_fn=lambda data: data.water_flow,
    ),
    PegelOnlineSensorEntityDescription(
        key="water_level",
        translation_key="water_level",
        state_class=SensorStateClass.MEASUREMENT,
        measurement_fn=lambda data: data.water_level,
    ),
    PegelOnlineSensorEntityDescription(
        key="water_temperature",
        translation_key="water_temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        measurement_fn=lambda data: data.water_temperature,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PegelOnlineConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PEGELONLINE sensor."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            PegelOnlineSensor(coordinator, description)
            for description in SENSORS
            if description.measurement_fn(coordinator.data) is not None
        ]
    )


class PegelOnlineSensor(PegelOnlineEntity, SensorEntity):
    """Representation of a PEGELONLINE sensor."""

    entity_description: PegelOnlineSensorEntityDescription

    def __init__(
        self,
        coordinator: PegelOnlineDataUpdateCoordinator,
        description: PegelOnlineSensorEntityDescription,
    ) -> None:
        """Initialize a PEGELONLINE sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self.station.uuid}_{description.key}"

        if description.device_class != SensorDeviceClass.PH:
            self._attr_native_unit_of_measurement = self.measurement.uom

        if self.station.latitude and self.station.longitude:
            self._attr_extra_state_attributes.update(
                {
                    ATTR_LATITUDE: self.station.latitude,
                    ATTR_LONGITUDE: self.station.longitude,
                }
            )

    @property
    def measurement(self) -> CurrentMeasurement:
        """Return the measurement data of the entity."""
        measurement = self.entity_description.measurement_fn(self.coordinator.data)
        assert measurement is not None  # we ensure existence in async_setup_entry
        return measurement

    @property
    def native_value(self) -> float:
        """Return the state of the device."""
        return self.measurement.value
