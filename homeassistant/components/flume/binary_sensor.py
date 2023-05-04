"""Flume binary sensors."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FLUME_AUTH,
    FLUME_DEVICES,
    FLUME_TYPE_BRIDGE,
    FLUME_TYPE_SENSOR,
    KEY_DEVICE_ID,
    KEY_DEVICE_LOCATION,
    KEY_DEVICE_LOCATION_NAME,
    KEY_DEVICE_TYPE,
    NOTIFICATION_HIGH_FLOW,
    NOTIFICATION_LEAK_DETECTED,
)
from .coordinator import (
    FlumeDeviceConnectionUpdateCoordinator,
    FlumeNotificationDataUpdateCoordinator,
)
from .entity import FlumeEntity
from .util import get_valid_flume_devices

BINARY_SENSOR_DESCRIPTION_CONNECTED = BinarySensorEntityDescription(
    name="Connected",
    key="connected",
)


@dataclass
class FlumeBinarySensorRequiredKeysMixin:
    """Mixin for required keys."""

    event_rule: str


@dataclass
class FlumeBinarySensorEntityDescription(
    BinarySensorEntityDescription, FlumeBinarySensorRequiredKeysMixin
):
    """Describes a binary sensor entity."""


FLUME_BINARY_NOTIFICATION_SENSORS: tuple[FlumeBinarySensorEntityDescription, ...] = (
    FlumeBinarySensorEntityDescription(
        key="leak",
        name="Leak detected",
        entity_category=EntityCategory.DIAGNOSTIC,
        event_rule=NOTIFICATION_LEAK_DETECTED,
        icon="mdi:pipe-leak",
    ),
    FlumeBinarySensorEntityDescription(
        key="flow",
        name="High flow",
        entity_category=EntityCategory.DIAGNOSTIC,
        event_rule=NOTIFICATION_HIGH_FLOW,
        icon="mdi:waves",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Flume binary sensor.."""
    flume_domain_data = hass.data[DOMAIN][config_entry.entry_id]
    flume_auth = flume_domain_data[FLUME_AUTH]
    flume_devices = flume_domain_data[FLUME_DEVICES]

    flume_entity_list: list[
        FlumeNotificationBinarySensor | FlumeConnectionBinarySensor
    ] = []

    connection_coordinator = FlumeDeviceConnectionUpdateCoordinator(
        hass=hass, flume_devices=flume_devices
    )
    notification_coordinator = FlumeNotificationDataUpdateCoordinator(
        hass=hass, auth=flume_auth
    )
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
