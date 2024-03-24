"""Support for AirGradient sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from airgradient.models import Status

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirGradientDataUpdateCoordinator
from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class AirGradientSensorEntityDescription(SensorEntityDescription):
    """Describes AirGradient sensor entity."""

    value_fn: Callable[[Status], StateType]


SENSOR_TYPES: tuple[AirGradientSensorEntityDescription, ...] = (
    AirGradientSensorEntityDescription(
        key="pm01",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda status: status.pm01,
    ),
    AirGradientSensorEntityDescription(
        key="pm02",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda status: status.pm02,
    ),
    AirGradientSensorEntityDescription(
        key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        value_fn=lambda status: status.pm10,
    ),
    AirGradientSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda status: status.ambient_temperature,
    ),
    AirGradientSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda status: status.relative_humidity,
    ),
    AirGradientSensorEntityDescription(
        key="boot",
        translation_key="boot_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.boot_time,
    ),
    AirGradientSensorEntityDescription(
        key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.signal_strength,
    ),
    AirGradientSensorEntityDescription(
        key="tvoc",
        translation_key="total_volatile_organic_component_index",
        value_fn=lambda status: status.total_volatile_organic_component_index,
    ),
    AirGradientSensorEntityDescription(
        key="nitrogen_index",
        translation_key="nitrogen_index",
        value_fn=lambda status: status.nitrogen_index,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AirGradient sensor entities based on a config entry."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        AirGradientSensor(coordinator, description) for description in SENSOR_TYPES
    )


class AirGradientSensor(
    CoordinatorEntity[AirGradientDataUpdateCoordinator], SensorEntity
):
    """Defines an AirGradient sensor."""

    _attr_has_entity_name = True

    entity_description: AirGradientSensorEntityDescription

    def __init__(
        self,
        coordinator: AirGradientDataUpdateCoordinator,
        description: AirGradientSensorEntityDescription,
    ) -> None:
        """Initialize airgradient sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.serial_number}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data.serial_number)},
            manufacturer="AirGradient",
            serial_number=coordinator.data.serial_number,
            sw_version=coordinator.data.firmware_version,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
