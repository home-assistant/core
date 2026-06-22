"""Support for SwitchBot binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass

import switchbot
from switchbot import LockStatus, SwitchbotModel

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

PARALLEL_UPDATES = 0

LOCK_ULTRA_BINARY_SENSORS = {"half_lock_calibration", "half_locked"}


@dataclass(frozen=True, kw_only=True)
class SwitchbotBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Switchbot binary sensor entity."""

    device_class_fn: Callable[[SwitchbotModel], BinarySensorDeviceClass] | None = None
    value_fn: Callable[[switchbot.SwitchbotDevice, str], bool | None] = (
        lambda device, key: device.parsed_data.get(key)
    )


BINARY_SENSOR_TYPES: dict[str, SwitchbotBinarySensorEntityDescription] = {
    "calibration": SwitchbotBinarySensorEntityDescription(
        key="calibration",
        translation_key="calibration",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "half_lock_calibration": SwitchbotBinarySensorEntityDescription(
        key="half_lock_calibration",
        translation_key="half_lock_calibration",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "half_locked": SwitchbotBinarySensorEntityDescription(
        key="half_locked",
        translation_key="half_locked",
        value_fn=lambda device, _: (
            None
            if (status := device.get_lock_status()) is None
            else status is LockStatus.HALF_LOCKED
        ),
    ),
    "motion_detected": SwitchbotBinarySensorEntityDescription(
        key="pir_state",
        device_class_fn=lambda model: {
            SwitchbotModel.PRESENCE_SENSOR: BinarySensorDeviceClass.OCCUPANCY,
        }.get(model, BinarySensorDeviceClass.MOTION),
    ),
    "contact_open": SwitchbotBinarySensorEntityDescription(
        key="contact_open",
        name=None,
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    "contact_timeout": SwitchbotBinarySensorEntityDescription(
        key="contact_timeout",
        translation_key="door_timeout",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "is_light": SwitchbotBinarySensorEntityDescription(
        key="is_light",
        device_class=BinarySensorDeviceClass.LIGHT,
    ),
    "door_open": SwitchbotBinarySensorEntityDescription(
        key="door_status",
        name=None,
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    "unclosed_alarm": SwitchbotBinarySensorEntityDescription(
        key="unclosed_alarm",
        translation_key="door_unclosed_alarm",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    "unlocked_alarm": SwitchbotBinarySensorEntityDescription(
        key="unlocked_alarm",
        translation_key="door_unlocked_alarm",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    "auto_lock_paused": SwitchbotBinarySensorEntityDescription(
        key="auto_lock_paused",
        translation_key="door_auto_lock_paused",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "leak": SwitchbotBinarySensorEntityDescription(
        key="leak",
        name=None,
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    "battery_charging": SwitchbotBinarySensorEntityDescription(
        key="battery_charging",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    "tamper_alarm": SwitchbotBinarySensorEntityDescription(
        key="tamper_alarm",
        device_class=BinarySensorDeviceClass.TAMPER,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Switchbot curtain based on a config entry."""
    coordinator = entry.runtime_data
    binary_sensors: set[str] = {
        bs for bs in coordinator.device.parsed_data if bs in BINARY_SENSOR_TYPES
    }
    if coordinator.model is SwitchbotModel.LOCK_ULTRA:
        binary_sensors.update(LOCK_ULTRA_BINARY_SENSORS)
    async_add_entities(
        SwitchBotBinarySensor(coordinator, binary_sensor)
        for binary_sensor in binary_sensors
    )


class SwitchBotBinarySensor(SwitchbotEntity, BinarySensorEntity):
    """Representation of a Switchbot binary sensor."""

    entity_description: SwitchbotBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        binary_sensor: str,
    ) -> None:
        """Initialize the Switchbot sensor."""
        super().__init__(coordinator)
        self._sensor = binary_sensor
        self._attr_unique_id = f"{coordinator.base_unique_id}-{binary_sensor}"
        self.entity_description = BINARY_SENSOR_TYPES[binary_sensor]
        if self.entity_description.device_class_fn:
            self._attr_device_class = self.entity_description.device_class_fn(
                coordinator.model
            )

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._device, self._sensor)
