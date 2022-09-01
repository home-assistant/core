"""Alert sensors."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    FLUME_AUTH,
    FLUME_DEVICES,
    FLUME_TYPE_SENSOR,
    KEY_DEVICE_ID,
    KEY_DEVICE_TYPE,
    NOTIFICATION_BRIDGE_DISCONNECT,
    NOTIFICATION_HIGH_FLOW,
    NOTIFICATION_LEAK_DETECTED,
)
from .coordinator import FlumeNotificationDataUpdateCoordinator
from .entity import FlumeEntity


@dataclass
class FlumeBinarySensorRequiredKeysMixin:
    """Mixin for required keys."""

    event_rule: str


@dataclass
class FlumeBinarySensorEntityDescription(
    BinarySensorEntityDescription, FlumeBinarySensorRequiredKeysMixin
):
    """Describes a binary sensor entity."""


FLUME_BINARY_SENSORS: tuple[FlumeBinarySensorEntityDescription, ...] = (
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
    FlumeBinarySensorEntityDescription(
        key="bridge",
        name="Bridge",
        entity_category=EntityCategory.DIAGNOSTIC,
        event_rule=NOTIFICATION_BRIDGE_DISCONNECT,
        icon="mdi:bridge",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
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

    flume_entity_list = []

    notification_coordinator = FlumeNotificationDataUpdateCoordinator(
        hass=hass, auth=flume_auth
    )

    for device in flume_devices.device_list:
        if device[KEY_DEVICE_TYPE] != FLUME_TYPE_SENSOR:
            continue

        device_id = device[KEY_DEVICE_ID]

        flume_entity_list.extend(
            [
                FlumeBinarySensor(
                    coordinator=notification_coordinator,
                    description=description,
                    device_id=device_id,
                )
                for description in FLUME_BINARY_SENSORS
            ]
        )

    if flume_entity_list:
        async_add_entities(flume_entity_list)


class FlumeBinarySensor(FlumeEntity, BinarySensorEntity):
    """Binary sensor class."""

    entity_description: FlumeBinarySensorEntityDescription
    coordinator: FlumeNotificationDataUpdateCoordinator

    @property
    def is_on(self) -> bool:
        """Return on state."""

        rule = self.entity_description.event_rule

        # The default notification value for notifications will be False, which means the notification
        # is not currently active. Bridge notifications, on the other hand, which are of Connectivity
        # class need to default to true which shows the unit IS connected. In the absence of an actual
        # notification from the coordinator this value will be used - as the "initial" or default value
        initial_value = (
            self.entity_description.device_class == BinarySensorDeviceClass.CONNECTIVITY
        )

        value = self.coordinator.active_notifications_by_device.get(
            self.device_id, {}
        ).get(rule, initial_value)

        return value
