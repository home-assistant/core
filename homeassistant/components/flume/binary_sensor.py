"""Flume binary sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    FLUME_TYPE_BRIDGE,
    FLUME_TYPE_SENSOR,
    KEY_DEVICE_ID,
    KEY_DEVICE_LOCATION,
    KEY_DEVICE_LOCATION_NAME,
    KEY_DEVICE_TYPE,
    NOTIFICATION_HIGH_FLOW,
    NOTIFICATION_LEAK_DETECTED,
    NOTIFICATION_LOW_BATTERY,
)
from .coordinator import (
    FlumeConfigEntry,
    FlumeDeviceConnectionUpdateCoordinator,
    FlumeNotificationDataUpdateCoordinator,
)
from .entity import FlumeEntity
from .util import get_valid_flume_devices

BINARY_SENSOR_DESCRIPTION_CONNECTED = BinarySensorEntityDescription(
    key="connected", device_class=BinarySensorDeviceClass.CONNECTIVITY
)


@dataclass(frozen=True, kw_only=True)
class FlumeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a binary sensor entity."""

    event_rule: str


FLUME_BINARY_NOTIFICATION_SENSORS: tuple[FlumeBinarySensorEntityDescription, ...] = (
    FlumeBinarySensorEntityDescription(
        key="leak",
        translation_key="leak",
        entity_category=EntityCategory.DIAGNOSTIC,
        event_rule=NOTIFICATION_LEAK_DETECTED,
    ),
    FlumeBinarySensorEntityDescription(
        key="flow",
        translation_key="flow",
        entity_category=EntityCategory.DIAGNOSTIC,
        event_rule=NOTIFICATION_HIGH_FLOW,
    ),
    FlumeBinarySensorEntityDescription(
        key="low_battery",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.BATTERY,
        event_rule=NOTIFICATION_LOW_BATTERY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FlumeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Flume binary sensor.."""
    flume_domain_data = config_entry.runtime_data
    flume_devices = flume_domain_data.devices

    flume_entity_list: list[
        FlumeNotificationBinarySensor | FlumeConnectionBinarySensor
    ] = []

    connection_coordinator = FlumeDeviceConnectionUpdateCoordinator(
        hass=hass, config_entry=config_entry, flume_devices=flume_devices
    )
    notification_coordinator = flume_domain_data.notifications_coordinator
    flume_devices = get_valid_flume_devices(flume_devices)
    for device in flume_devices:
        device_id = device[KEY_DEVICE_ID]
        device_location_name = device[KEY_DEVICE_LOCATION][KEY_DEVICE_LOCATION_NAME]

        connection_sensor = FlumeConnectionBinarySensor(
            coordinator=connection_coordinator,
            description=BINARY_SENSOR_DESCRIPTION_CONNECTED,
            device_id=device_id,
            location_name=device_location_name,
            is_bridge=(device[KEY_DEVICE_TYPE] is FLUME_TYPE_BRIDGE),
        )

        flume_entity_list.append(connection_sensor)

        if device[KEY_DEVICE_TYPE] != FLUME_TYPE_SENSOR:
            continue

        # Build notification sensors
        flume_entity_list.extend(
            [
                FlumeNotificationBinarySensor(
                    coordinator=notification_coordinator,
                    description=description,
                    device_id=device_id,
                    location_name=device_location_name,
                )
                for description in FLUME_BINARY_NOTIFICATION_SENSORS
            ]
        )

    async_add_entities(flume_entity_list)


class FlumeNotificationBinarySensor(
    FlumeEntity[FlumeNotificationDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor class."""

    entity_description: FlumeBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return on state."""
        return bool(
            (
                notifications := self.coordinator.active_notifications_by_device.get(
                    self.device_id
                )
            )
            and self.entity_description.event_rule in notifications
        )


class FlumeConnectionBinarySensor(
    FlumeEntity[FlumeDeviceConnectionUpdateCoordinator], BinarySensorEntity
):
    """Binary Sensor class for WIFI Connection status."""

    entity_description: FlumeBinarySensorEntityDescription
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Return connection status."""
        return bool(
            (connected := self.coordinator.connected) and connected[self.device_id]
        )
