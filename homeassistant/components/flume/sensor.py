"""Sensor for displaying the number of result from Flume."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from numbers import Number

from pyflume import FlumeData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import VOLUME_GALLONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_SCAN_INTERVAL,
    DOMAIN,
    FLUME_AUTH,
    FLUME_DEVICES,
    FLUME_HTTP_SESSION,
    FLUME_TYPE_SENSOR,
    KEY_DEVICE_ID,
    KEY_DEVICE_LOCATION,
    KEY_DEVICE_LOCATION_NAME,
    KEY_DEVICE_LOCATION_TIMEZONE,
    KEY_DEVICE_TYPE,
    NOTIFICATION_HIGH_FLOW,
    NOTIFICATION_LEAK_DETECTED,
)
from .coordinator import (
    FlumeDeviceDataUpdateCoordinator,
    FlumeNotificationDataUpdateCoordinator,
)
from .entity import FlumeEntity, FlumeNotificationSensorRequiredKeysMixin
from .util import get_valid_flume_devices


@dataclass
class FlumeNotificationSensorEntityDescription(
    SensorEntityDescription, FlumeNotificationSensorRequiredKeysMixin
):
    """Describe a notification based sensor."""


FLUME_QUERIES_SENSOR: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="current_interval",
        name="Current",
        native_unit_of_measurement=f"{VOLUME_GALLONS}/m",
    ),
    SensorEntityDescription(
        key="month_to_date",
        name="Current Month",
        native_unit_of_measurement=VOLUME_GALLONS,
        device_class=SensorDeviceClass.VOLUME,
    ),
    SensorEntityDescription(
        key="week_to_date",
        name="Current Week",
        native_unit_of_measurement=VOLUME_GALLONS,
        device_class=SensorDeviceClass.VOLUME,
    ),
    SensorEntityDescription(
        key="today",
        name="Current Day",
        native_unit_of_measurement=VOLUME_GALLONS,
        device_class=SensorDeviceClass.VOLUME,
    ),
    SensorEntityDescription(
        key="last_60_min",
        name="60 Minutes",
        native_unit_of_measurement=f"{VOLUME_GALLONS}/h",
    ),
    SensorEntityDescription(
        key="last_24_hrs",
        name="24 Hours",
        native_unit_of_measurement=f"{VOLUME_GALLONS}/d",
    ),
    SensorEntityDescription(
        key="last_30_days",
        name="30 Days",
        native_unit_of_measurement=f"{VOLUME_GALLONS}/mo",
    ),
)


FLUME_NOTIFICATION_SENSORS: tuple[FlumeNotificationSensorEntityDescription, ...] = (
    FlumeNotificationSensorEntityDescription(
        key="high_flow_age",
        name="High flow age",
        device_class=SensorDeviceClass.TIMESTAMP,
        event_rule=NOTIFICATION_HIGH_FLOW,
    ),
    FlumeNotificationSensorEntityDescription(
        key="leak_age",
        name="Leak detected age",
        device_class=SensorDeviceClass.TIMESTAMP,
        event_rule=NOTIFICATION_LEAK_DETECTED,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Flume sensor."""

    flume_domain_data = hass.data[DOMAIN][config_entry.entry_id]
    flume_devices = flume_domain_data[FLUME_DEVICES]
    flume_auth = flume_domain_data[FLUME_AUTH]
    http_session = flume_domain_data[FLUME_HTTP_SESSION]
    flume_devices = [
        device
        for device in get_valid_flume_devices(flume_devices)
        if device[KEY_DEVICE_TYPE] == FLUME_TYPE_SENSOR
    ]
    flume_entity_list: list[FlumeSensor | FlumeNotificationSensor] = []
    for device in flume_devices:

        device_id = device[KEY_DEVICE_ID]
        device_timezone = device[KEY_DEVICE_LOCATION][KEY_DEVICE_LOCATION_TIMEZONE]
        device_location_name = device[KEY_DEVICE_LOCATION][KEY_DEVICE_LOCATION_NAME]

        flume_device = FlumeData(
            flume_auth,
            device_id,
            device_timezone,
            scan_interval=DEVICE_SCAN_INTERVAL,
            update_on_init=False,
            http_session=http_session,
        )

        data_coordinator = FlumeDeviceDataUpdateCoordinator(
            hass=hass, flume_device=flume_device
        )

        flume_entity_list.extend(
            [
                FlumeSensor(
                    coordinator=data_coordinator,
                    description=description,
                    device_id=device_id,
                    location_name=device_location_name,
                )
                for description in FLUME_QUERIES_SENSOR
            ]
        )

        notification_coordinator = FlumeNotificationDataUpdateCoordinator(
            hass=hass, auth=flume_auth
        )

        flume_entity_list.extend(
            [
                FlumeNotificationSensor(
                    coordinator=notification_coordinator,
                    description=description,
                    device_id=device_id,
                    location_name=device_location_name,
                )
                for description in FLUME_NOTIFICATION_SENSORS
            ]
        )

    async_add_entities(flume_entity_list)


class FlumeSensor(FlumeEntity, SensorEntity):
    """Representation of the Flume sensor."""

    coordinator: FlumeDeviceDataUpdateCoordinator

    @property
    def native_value(self):
        """Return the state of the sensor."""
        sensor_key = self.entity_description.key
        if sensor_key not in self.coordinator.flume_device.values:
            return None

        return _format_state_value(self.coordinator.flume_device.values[sensor_key])


def _format_state_value(value):
    return round(value, 1) if isinstance(value, Number) else None


class FlumeNotificationSensor(FlumeEntity, SensorEntity):
    """Represents a notification backed flume diagnostic sensor."""

    entity_description: FlumeNotificationSensorEntityDescription
    coordinator: FlumeNotificationDataUpdateCoordinator
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> datetime | None:
        """Return time since last error or None."""

        if notifications := self.coordinator.active_notifications_by_device.get(
            self.device_id
        ):
            return notifications.get(self.entity_description.event_rule)
        return None
