"""Support for DROP binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_DEVICE_TYPE,
    DEV_ALERT,
    DEV_HUB,
    DEV_LEAK_DETECTOR,
    DEV_PROTECTION_VALVE,
    DEV_PUMP_CONTROLLER,
    DEV_RO_FILTER,
    DEV_SALT_SENSOR,
    DEV_SOFTENER,
)
from .coordinator import DROPConfigEntry, DROPDeviceDataUpdateCoordinator
from .entity import DROPEntity

_LOGGER = logging.getLogger(__name__)


# Binary sensor type constants
ALERT_SENSOR = "alert_sensor"
LEAK_DETECTED = "leak"
PENDING_NOTIFICATION = "pending_notification"
POWER = "power"
PUMP_STATUS = "pump"
RESERVE_IN_USE = "reserve_in_use"
SALT_LOW = "salt"


@dataclass(kw_only=True, frozen=True)
class DROPBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes DROP binary sensor entity."""

    value_fn: Callable[[DROPDeviceDataUpdateCoordinator], int | None]


BINARY_SENSORS: list[DROPBinarySensorEntityDescription] = [
    DROPBinarySensorEntityDescription(
        key=LEAK_DETECTED,
        translation_key=LEAK_DETECTED,
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_fn=lambda device: device.drop_api.leak_detected(),
    ),
    DROPBinarySensorEntityDescription(
        key=PENDING_NOTIFICATION,
        translation_key=PENDING_NOTIFICATION,
        value_fn=lambda device: device.drop_api.notification_pending(),
    ),
    DROPBinarySensorEntityDescription(
        key=SALT_LOW,
        translation_key=SALT_LOW,
        value_fn=lambda device: device.drop_api.salt_low(),
    ),
    DROPBinarySensorEntityDescription(
        key=RESERVE_IN_USE,
        translation_key=RESERVE_IN_USE,
        value_fn=lambda device: device.drop_api.reserve_in_use(),
    ),
    DROPBinarySensorEntityDescription(
        key=PUMP_STATUS,
        translation_key=PUMP_STATUS,
        value_fn=lambda device: device.drop_api.pump_status(),
    ),
    DROPBinarySensorEntityDescription(
        key=ALERT_SENSOR,
        translation_key=ALERT_SENSOR,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda device: device.drop_api.sensor_high(),
    ),
    DROPBinarySensorEntityDescription(
        key=POWER,
        translation_key=None,  # Use name provided by binary sensor device class
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda device: device.drop_api.power(),
    ),
]

# Defines which binary sensors are used by each device type
DEVICE_BINARY_SENSORS: dict[str, list[str]] = {
    DEV_ALERT: [ALERT_SENSOR, POWER],
    DEV_HUB: [LEAK_DETECTED, PENDING_NOTIFICATION],
    DEV_LEAK_DETECTOR: [LEAK_DETECTED],
    DEV_PROTECTION_VALVE: [LEAK_DETECTED],
    DEV_PUMP_CONTROLLER: [LEAK_DETECTED, PUMP_STATUS],
    DEV_RO_FILTER: [LEAK_DETECTED],
    DEV_SALT_SENSOR: [SALT_LOW],
    DEV_SOFTENER: [RESERVE_IN_USE],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DROPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DROP binary sensors from config entry."""
    _LOGGER.debug(
        "Set up binary sensor for device type %s with entry_id is %s",
        config_entry.data[CONF_DEVICE_TYPE],
        config_entry.entry_id,
    )

    coordinator = config_entry.runtime_data
    if config_entry.data[CONF_DEVICE_TYPE] in DEVICE_BINARY_SENSORS:
        async_add_entities(
            DROPBinarySensor(coordinator, sensor)
            for sensor in BINARY_SENSORS
            if sensor.key in DEVICE_BINARY_SENSORS[config_entry.data[CONF_DEVICE_TYPE]]
        )


class DROPBinarySensor(DROPEntity, BinarySensorEntity):
    """Representation of a DROP binary sensor."""

    entity_description: DROPBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: DROPDeviceDataUpdateCoordinator,
        entity_description: DROPBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(entity_description.key, coordinator)
        self.entity_description = entity_description

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator) == 1
