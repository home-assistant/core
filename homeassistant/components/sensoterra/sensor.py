"""Sensoterra devices."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
from .coordinator import SensoterraCoordinator, SensoterraSensor
from .models import ProbeSensorType

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
    def _async_add_devices(st_sensors: list[SensoterraSensor]) -> None:
        async_add_devices(
            SensoterraEntity(coordinator, st_sensor.probe, st_sensor.sensor)
            for st_sensor in st_sensors
            if st_sensor.sensor.type.lower() in SENSORS
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
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator, context=sensor.id)

        self._attr_unique_id = sensor.id
        self._attr_translation_placeholders = {
            "depth": "?" if sensor.depth is None else str(sensor.depth)
        }

        self.entity_description = SENSORS[ProbeSensorType[sensor.type]]

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
    def native_value(self) -> StateType:
        """Return the sensor value reported by the API."""
        sensor = self.coordinator.get_sensor(self._attr_unique_id)
        if sensor is None:
            return None

        # Expire sensor if no update within the last few days.
        expiration = datetime.now(UTC) - timedelta(days=SENSOR_EXPIRATION_DAYS)
        if sensor.timestamp is None or sensor.timestamp < expiration:
            return None

        return sensor.value  # type: ignore[no-any-return]
