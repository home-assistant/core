"""Binary sensors for Yale Alarm."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR, DOMAIN
from .coordinator import YaleDataUpdateCoordinator
from .entity import YaleAlarmEntity, YaleEntity

SENSOR_TYPES = (
    BinarySensorEntityDescription(
        key="acfail",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="power_loss",
    ),
    BinarySensorEntityDescription(
        key="battery",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="battery",
    ),
    BinarySensorEntityDescription(
        key="tamper",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="tamper",
    ),
    BinarySensorEntityDescription(
        key="jam",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="jam",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Yale binary sensor entry."""

    coordinator: YaleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]
    sensors: list[YaleDoorSensor | YaleProblemSensor] = []
    for data in coordinator.data["door_windows"]:
        sensors.append(YaleDoorSensor(coordinator, data))
    for description in SENSOR_TYPES:
        sensors.append(YaleProblemSensor(coordinator, description))

    async_add_entities(sensors)


class YaleDoorSensor(YaleEntity, BinarySensorEntity):
    """Representation of a Yale door sensor."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return bool(self.coordinator.data["sensor_map"][self._attr_unique_id] == "open")


class YaleProblemSensor(YaleAlarmEntity, BinarySensorEntity):
    """Representation of a Yale problem sensor."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: YaleDataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initiate Yale Problem Sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.entry.entry_id}-{entity_description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return bool(
            self.coordinator.data["status"][self.entity_description.key]
            != "main.normal"
        )
