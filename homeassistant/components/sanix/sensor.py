"""Platform for Sensor integration."""
from datetime import date, datetime

from sanix.const import (
    ATTR_API_BATTERY,
    ATTR_API_DEVICE_NO,
    ATTR_API_DISTANCE,
    ATTR_API_FILL_PERC,
    ATTR_API_SERVICE_DATE,
    ATTR_API_SSID,
    ATTR_API_TIME,
)

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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import SanixCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ATTR_API_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_API_SERVICE_DATE,
        device_class=SensorDeviceClass.DATE,
        translation_key="service_date",
    ),
    SensorEntityDescription(
        key=ATTR_API_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="time",
    ),
    SensorEntityDescription(
        key=ATTR_API_FILL_PERC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="fill_percentage",
        icon="mdi:water-percent",
    ),
    SensorEntityDescription(
        key=ATTR_API_SSID, translation_key="ssid", entity_registry_enabled_default=False
    ),
    SensorEntityDescription(
        key=ATTR_API_DEVICE_NO,
        translation_key="device_no",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sanix Sensor entities based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SanixSensorEntity(
            coordinator=coordinator,
            description=description,
        )
        for description in SENSOR_TYPES
    )


class SanixSensorEntity(CoordinatorEntity[SanixCoordinator], SensorEntity):
    """Sanix Sensor entity."""

    _attr_has_entity_name = True
    entity_description: SensorEntityDescription

    def __init__(
        self,
        *,
        coordinator: SanixCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        serial_no = str(coordinator.config_entry.unique_id)

        self._attr_unique_id = f"{serial_no}-{description.key}"
        self.entity_description = description

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, serial_no)},
            manufacturer=MANUFACTURER,
            serial_number=serial_no,
        )

    @property
    def native_value(self) -> int | datetime | date | str:
        """Return the state of the sensor."""
        return getattr(self.coordinator.data, self.entity_description.key)
