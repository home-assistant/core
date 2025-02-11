"""Platform for Sanix integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

from sanix.const import (
    ATTR_API_BATTERY,
    ATTR_API_DEVICE_NO,
    ATTR_API_DISTANCE,
    ATTR_API_FILL_PERC,
    ATTR_API_SERVICE_DATE,
    ATTR_API_SSID,
)
from sanix.models import Measurement

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import SanixCoordinator


@dataclass(frozen=True, kw_only=True)
class SanixSensorEntityDescription(SensorEntityDescription):
    """Class describing Sanix Sensor entities."""

    native_value_fn: Callable[[Measurement], int | datetime | date | str]


SENSOR_TYPES: tuple[SanixSensorEntityDescription, ...] = (
    SanixSensorEntityDescription(
        key=ATTR_API_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_value_fn=lambda data: data.battery,
    ),
    SanixSensorEntityDescription(
        key=ATTR_API_DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_value_fn=lambda data: data.distance,
    ),
    SanixSensorEntityDescription(
        key=ATTR_API_SERVICE_DATE,
        translation_key=ATTR_API_SERVICE_DATE,
        device_class=SensorDeviceClass.DATE,
        native_value_fn=lambda data: data.service_date,
    ),
    SanixSensorEntityDescription(
        key=ATTR_API_FILL_PERC,
        translation_key=ATTR_API_FILL_PERC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_value_fn=lambda data: data.fill_perc,
    ),
    SanixSensorEntityDescription(
        key=ATTR_API_SSID,
        translation_key=ATTR_API_SSID,
        entity_registry_enabled_default=False,
        native_value_fn=lambda data: data.ssid,
    ),
    SanixSensorEntityDescription(
        key=ATTR_API_DEVICE_NO,
        translation_key=ATTR_API_DEVICE_NO,
        entity_registry_enabled_default=False,
        native_value_fn=lambda data: data.device_no,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sanix Sensor entities based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SanixSensorEntity(coordinator, description) for description in SENSOR_TYPES
    )


class SanixSensorEntity(CoordinatorEntity[SanixCoordinator], SensorEntity):
    """Sanix Sensor entity."""

    _attr_has_entity_name = True
    entity_description: SanixSensorEntityDescription

    def __init__(
        self,
        coordinator: SanixCoordinator,
        description: SanixSensorEntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        serial_no = str(coordinator.config_entry.unique_id)

        self._attr_unique_id = f"{serial_no}-{description.key}"
        self.entity_description = description

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_no)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            serial_number=serial_no,
        )

    @property
    def native_value(self) -> int | datetime | date | str:
        """Return the state of the sensor."""
        return self.entity_description.native_value_fn(self.coordinator.data)
