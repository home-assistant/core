"""Sensoterra devices."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum, auto

from sensoterra.probe import Probe, Sensor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SensoterraConfigEntry
from .const import CONFIGURATION_URL, DOMAIN, SENSOR_EXPIRATION_DAYS
from .coordinator import SensoterraCoordinator


class ProbeSensorType(StrEnum):
    """Generic sensors within a Sensoterra probe."""

    MOISTURE = auto()
    SI = auto()
    TEMPERATURE = auto()
    BATTERY = auto()
    RSSI = auto()


SENSORS: dict[ProbeSensorType, SensorEntityDescription] = {
    ProbeSensorType.MOISTURE: SensorEntityDescription(
        key=ProbeSensorType.MOISTURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.MOISTURE,
        native_unit_of_measurement=PERCENTAGE,
        translation_key="soil_moisture_at_cm",
    ),
    ProbeSensorType.SI: SensorEntityDescription(
        key=ProbeSensorType.SI,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        translation_key="si_at_cm",
    ),
    ProbeSensorType.TEMPERATURE: SensorEntityDescription(
        key=ProbeSensorType.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ProbeSensorType.BATTERY: SensorEntityDescription(
        key=ProbeSensorType.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ProbeSensorType.RSSI: SensorEntityDescription(
        key=ProbeSensorType.RSSI,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensoterraConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up Sensoterra sensor."""

    coordinator = entry.runtime_data

    @callback
    def _async_add_devices(probes: list[Probe]) -> None:
        aha = coordinator.async_contexts()
        current_sensors = set(aha)
        async_add_devices(
            SensoterraEntity(
                coordinator,
                probe,
                sensor,
                SENSORS[ProbeSensorType[sensor.type]],
            )
            for probe in probes
            for sensor in probe.sensors()
            if sensor.type is not None
            and sensor.type.lower() in SENSORS
            and sensor.id not in current_sensors
        )

    coordinator.add_devices_callback = _async_add_devices

    _async_add_devices(coordinator.data)


class SensoterraEntity(CoordinatorEntity[SensoterraCoordinator], SensorEntity):
    """Sensoterra sensor like a soil moisture or temperature sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SensoterraCoordinator,
        probe: Probe,
        sensor: Sensor,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, context=sensor.id)

        self._sensor_id = sensor.id
        self._attr_unique_id = self._sensor_id
        self._attr_translation_placeholders = {
            "depth": "?" if sensor.depth is None else str(sensor.depth)
        }

        self.entity_description = entity_description

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, probe.serial)},
            name=probe.name,
            model=probe.sku,
            manufacturer="Sensoterra",
            serial_number=probe.serial,
            suggested_area=probe.location,
            configuration_url=CONFIGURATION_URL,
        )

    @property
    def sensor(self) -> Sensor | None:
        """Return the sensor, or None if it doesn't exist."""
        return self.coordinator.get_sensor(self._sensor_id)

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        assert self.sensor
        return self.sensor.value

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available or (sensor := self.sensor) is None:
            return False

        if sensor.timestamp is None:
            return False

        # Expire sensor if no update within the last few days.
        expiration = datetime.now(UTC) - timedelta(days=SENSOR_EXPIRATION_DAYS)
        return sensor.timestamp >= expiration
