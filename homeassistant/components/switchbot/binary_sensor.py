"""Support for SwitchBot binary sensors."""
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

from .const import DOMAIN
from .coordinator import SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

PARALLEL_UPDATES = 0


@dataclass
class SwitchbotBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing SwitchBot binary sensor entities."""

    name: str | None = None


BINARY_SENSOR_TYPES = {
    "calibration": SwitchbotBinarySensorEntityDescription(
        key="calibration",
        name="Calibration",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "motion_detected": SwitchbotBinarySensorEntityDescription(
        key="pir_state",
        name="Motion detected",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "contact_open": SwitchbotBinarySensorEntityDescription(
        key="contact_open",
        name="Door open",
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    "contact_timeout": SwitchbotBinarySensorEntityDescription(
        key="contact_timeout",
        name="Door timeout",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "is_light": SwitchbotBinarySensorEntityDescription(
        key="is_light",
        name="Light",
        device_class=BinarySensorDeviceClass.LIGHT,
    ),
    "door_open": SwitchbotBinarySensorEntityDescription(
        key="door_status",
        name="Door status",
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    "unclosed_alarm": SwitchbotBinarySensorEntityDescription(
        key="unclosed_alarm",
        name="Door unclosed alarm",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    "unlocked_alarm": SwitchbotBinarySensorEntityDescription(
        key="unlocked_alarm",
        name="Door unlocked alarm",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    "auto_lock_paused": SwitchbotBinarySensorEntityDescription(
        key="auto_lock_paused",
        name="Door auto-lock paused",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Switchbot curtain based on a config entry."""
    coordinator: SwitchbotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
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
        self._attr_name = self.entity_description.name

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.parsed_data[self._sensor]
