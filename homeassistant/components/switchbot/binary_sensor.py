"""Support for SwitchBot binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

PARALLEL_UPDATES = 0

BINARY_SENSOR_TYPES: dict[str, BinarySensorEntityDescription] = {
    "calibration": BinarySensorEntityDescription(
        key="calibration",
        translation_key="calibration",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "motion_detected": BinarySensorEntityDescription(
        key="pir_state",
        name=None,
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "contact_open": BinarySensorEntityDescription(
        key="contact_open",
        name=None,
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    "contact_timeout": BinarySensorEntityDescription(
        key="contact_timeout",
        translation_key="door_timeout",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "is_light": BinarySensorEntityDescription(
        key="is_light",
        device_class=BinarySensorDeviceClass.LIGHT,
    ),
    "door_open": BinarySensorEntityDescription(
        key="door_status",
        name=None,
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    "unclosed_alarm": BinarySensorEntityDescription(
        key="unclosed_alarm",
        translation_key="door_unclosed_alarm",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    "unlocked_alarm": BinarySensorEntityDescription(
        key="unlocked_alarm",
        translation_key="door_unlocked_alarm",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    "auto_lock_paused": BinarySensorEntityDescription(
        key="auto_lock_paused",
        translation_key="door_auto_lock_paused",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "leak": BinarySensorEntityDescription(
        key="leak",
        name=None,
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Switchbot curtain based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        SwitchBotBinarySensor(coordinator, binary_sensor)
        for binary_sensor in coordinator.device.parsed_data
        if binary_sensor in BINARY_SENSOR_TYPES
    )


class SwitchBotBinarySensor(SwitchbotEntity, BinarySensorEntity):
    """Representation of a Switchbot binary sensor."""

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

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.parsed_data[self._sensor]
