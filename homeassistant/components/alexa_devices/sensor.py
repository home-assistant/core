"""Support for sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from aioamazondevices.const.schedules import (
    NOTIFICATION_ALARM,
    NOTIFICATION_REMINDER,
    NOTIFICATION_TIMER,
)
from aioamazondevices.structures import AmazonDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import CATEGORY_NOTIFICATIONS, CATEGORY_SENSORS
from .coordinator import AmazonConfigEntry
from .entity import AmazonEntity
from .utils import async_remove_unsupported_notification_sensors

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AmazonSensorEntityDescription(SensorEntityDescription):
    """Amazon Devices sensor entity description."""

    native_unit_of_measurement_fn: Callable[[AmazonDevice, str], str] | None = None
    is_available_fn: Callable[[AmazonDevice, str], bool] = lambda device, key: (
        device.online
        and (sensor := device.sensors.get(key)) is not None
        and sensor.error is False
    )
    category: str = CATEGORY_SENSORS


@dataclass(frozen=True, kw_only=True)
class AmazonNotificationEntityDescription(SensorEntityDescription):
    """Amazon Devices notification entity description."""

    native_unit_of_measurement_fn: Callable[[AmazonDevice, str], str] | None = None
    is_available_fn: Callable[[AmazonDevice, str], bool] = lambda device, key: (
        device.online
        and (notification := device.notifications.get(key)) is not None
        and notification.next_occurrence is not None
    )
    category: str = CATEGORY_NOTIFICATIONS


SENSORS: Final = (
    AmazonSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement_fn=lambda device, key: (
            UnitOfTemperature.CELSIUS
            if key in device.sensors and device.sensors[key].scale == "CELSIUS"
            else UnitOfTemperature.FAHRENHEIT
        ),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AmazonSensorEntityDescription(
        key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AmazonSensorEntityDescription(
        key="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AmazonSensorEntityDescription(
        key="PM10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AmazonSensorEntityDescription(
        key="PM25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AmazonSensorEntityDescription(
        key="CO",
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AmazonSensorEntityDescription(
        key="VOC",
        # No device class as this is an index not a concentration
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="voc_index",
    ),
    AmazonSensorEntityDescription(
        key="Air Quality",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)
NOTIFICATIONS: Final = (
    AmazonNotificationEntityDescription(
        key=NOTIFICATION_ALARM,
        translation_key="alarm",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    AmazonNotificationEntityDescription(
        key=NOTIFICATION_REMINDER,
        translation_key="reminder",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    AmazonNotificationEntityDescription(
        key=NOTIFICATION_TIMER,
        translation_key="timer",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Amazon Devices sensors based on a config entry."""

    coordinator = entry.runtime_data

    # Remove notification sensors from unsupported devices
    await async_remove_unsupported_notification_sensors(hass, coordinator)

    known_devices: set[str] = set()

    def _check_device() -> None:
        current_devices = set(coordinator.data)
        new_devices = current_devices - known_devices
        if new_devices:
            known_devices.update(new_devices)
            sensors_list = [
                AmazonSensorEntity(coordinator, serial_num, sensor_desc)
                for sensor_desc in SENSORS
                for serial_num in new_devices
                if coordinator.data[serial_num].sensors.get(sensor_desc.key) is not None
            ]
            notifications_list = [
                AmazonSensorEntity(coordinator, serial_num, notification_desc)
                for notification_desc in NOTIFICATIONS
                for serial_num in new_devices
                if coordinator.data[serial_num].notifications_supported
            ]
            async_add_entities(sensors_list + notifications_list)

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


class AmazonSensorEntity(AmazonEntity, SensorEntity):
    """Sensor device."""

    entity_description: (
        AmazonSensorEntityDescription | AmazonNotificationEntityDescription
    )

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor."""
        if self.entity_description.native_unit_of_measurement_fn:
            return self.entity_description.native_unit_of_measurement_fn(
                self.device, self.entity_description.key
            )

        return super().native_unit_of_measurement

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        # Sensors
        if self.entity_description.category == CATEGORY_SENSORS:
            return self.device.sensors[self.entity_description.key].value
        # Notifications
        return self.device.notifications[self.entity_description.key].next_occurrence

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.entity_description.is_available_fn(
                self.device, self.entity_description.key
            )
            and super().available
        )
