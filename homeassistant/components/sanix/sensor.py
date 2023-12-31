"""Platform for Sensor integration."""
from collections.abc import Callable
from dataclasses import dataclass
import datetime
import logging
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_API_BATTERY,
    ATTR_API_DEVICE_NO,
    ATTR_API_DISTANCE,
    ATTR_API_FILL_PERCENTAGE,
    ATTR_API_SERVICE_DATE,
    ATTR_API_SSID,
    ATTR_API_TIME,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import SanixCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SanixSensorEntityDescription(SensorEntityDescription):
    """Class describing Sanix Sensor entities."""

    attr: Callable[[dict[str, Any]], dict[str, Any]] = lambda data: {}


SENSOR_TYPES: tuple[SanixSensorEntityDescription, ...] = (
    SanixSensorEntityDescription(
        key=ATTR_API_BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SanixSensorEntityDescription(
        key=ATTR_API_DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS.value,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SanixSensorEntityDescription(
        key=ATTR_API_SERVICE_DATE,
        device_class=SensorDeviceClass.DATE,
        translation_key="service_date",
    ),
    SanixSensorEntityDescription(
        key=ATTR_API_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="time",
    ),
    SanixSensorEntityDescription(
        key=ATTR_API_FILL_PERCENTAGE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="fill_percentage",
        icon="mdi:water-percent",
    ),
    SanixSensorEntityDescription(key=ATTR_API_SSID, translation_key="ssid"),
    SanixSensorEntityDescription(key=ATTR_API_DEVICE_NO, translation_key="device_no"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sanix Sensor entities based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for description in SENSOR_TYPES:
        if coordinator.data.get(description.key):
            sensors.append(
                SanixSensor(coordinator, entry.title, str(entry.unique_id), description)
            )

    async_add_entities(sensors, False)


class SanixSensor(CoordinatorEntity[SanixCoordinator], SensorEntity):
    """Sanix Sensor entity."""

    _attr_has_entity_name = True
    entity_description: SanixSensorEntityDescription

    def __init__(
        self,
        coordinator: SanixCoordinator,
        name: str,
        serial_no: str,
        description: SanixSensorEntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{name}-{description.key}".lower()
        self._attr_native_value = self.format_value(
            coordinator.data[description.key], description.key
        )
        self.entity_description = description

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, name)},
            manufacturer=MANUFACTURER,
            name=name,
            serial_number=serial_no,
        )

    def format_value(self, value, key):
        """Format the value to the native format."""
        try:
            if key == ATTR_API_SERVICE_DATE:
                value = datetime.datetime.strptime(value, "%d.%m.%Y").date()
            elif key == ATTR_API_TIME:
                value = datetime.datetime.strptime(value, "%d.%m.%Y %H:%M:%S").replace(
                    tzinfo=ZoneInfo("Europe/Warsaw")
                )
        except ValueError:
            _LOGGER.warning(
                "Could not format the '%s' sensor. Retrieved value: %s", key, value
            )
            return None
        return value

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.format_value(
            self.coordinator.data[self.entity_description.key],
            self.entity_description.key,
        )
        self.async_write_ha_state()
