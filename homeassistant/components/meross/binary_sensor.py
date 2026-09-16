"""Binary sensors for Meross Bluetooth."""

from __future__ import annotations

from dataclasses import dataclass

from meross_ble import BATTERY_LOW_THRESHOLD, MerossModel, ms220_alarm_feature_enabled

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MerossBLEDataUpdateCoordinator, MerossConfigEntry
from .entity import MerossBLEEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MerossBLEBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Binary sensor mapped to a parsed_data key."""

    value_key: str


COMMON_BINARY_SENSORS: tuple[MerossBLEBinarySensorEntityDescription, ...] = (
    MerossBLEBinarySensorEntityDescription(
        key="battery_low",
        translation_key="battery_low",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="battery",
    ),
)

MS220_CORE_BINARY_SENSORS: tuple[MerossBLEBinarySensorEntityDescription, ...] = (
    MerossBLEBinarySensorEntityDescription(
        key="opening",
        translation_key="opening",
        device_class=BinarySensorDeviceClass.OPENING,
        value_key="door_open",
    ),
)

MS220_OPTIONAL_ALARM_SENSORS: tuple[MerossBLEBinarySensorEntityDescription, ...] = (
    MerossBLEBinarySensorEntityDescription(
        key="alarm_door_open_long",
        translation_key="alarm_door_open_long",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="alarm_door_open_long",
    ),
    MerossBLEBinarySensorEntityDescription(
        key="alarm_door_closed_long",
        translation_key="alarm_door_closed_long",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="alarm_door_closed_long",
    ),
    MerossBLEBinarySensorEntityDescription(
        key="alarm_vibration",
        translation_key="alarm_vibration",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_key="alarm_vibration",
    ),
)

MS420_BINARY_SENSORS: tuple[MerossBLEBinarySensorEntityDescription, ...] = (
    MerossBLEBinarySensorEntityDescription(
        key="water_leak",
        translation_key="water_leak",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_key="water_leak",
    ),
    MerossBLEBinarySensorEntityDescription(
        key="rain_detected",
        translation_key="rain_detected",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_key="rain_detected",
    ),
    MerossBLEBinarySensorEntityDescription(
        key="freeze_alarm",
        translation_key="freeze_alarm",
        device_class=BinarySensorDeviceClass.COLD,
        value_key="freeze_alarm",
    ),
)

BINARY_SENSORS_BY_MODEL: dict[
    MerossModel, tuple[MerossBLEBinarySensorEntityDescription, ...]
] = {
    MerossModel.MS120: COMMON_BINARY_SENSORS,
    MerossModel.MS220: (*COMMON_BINARY_SENSORS, *MS220_CORE_BINARY_SENSORS),
    MerossModel.MS420: (*COMMON_BINARY_SENSORS, *MS420_BINARY_SENSORS),
    MerossModel.MS700: COMMON_BINARY_SENSORS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MerossConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meross BLE binary sensors from a config entry."""
    coordinator = entry.runtime_data
    descriptions = BINARY_SENSORS_BY_MODEL.get(coordinator.model, ())
    entities: list[BinarySensorEntity] = [
        MerossBLEBinarySensor(coordinator, description)
        for description in descriptions
    ]
    entities.append(MerossBLEConnectivitySensor(coordinator))
    async_add_entities(entities)

    if coordinator.model is not MerossModel.MS220:
        return

    registry = er.async_get(hass)
    added_alarms: set[str] = set()

    for description in MS220_OPTIONAL_ALARM_SENSORS:
        unique_id = f"{coordinator.base_unique_id}-{description.key}"
        entity_id = registry.async_get_entity_id(
            Platform.BINARY_SENSOR, entry.domain, unique_id
        )
        if entity_id is None:
            continue
        enabled = ms220_alarm_feature_enabled(description.key, coordinator.device.data)
        if enabled is None:
            continue
        if not enabled:
            registry.async_remove(entity_id)

    @callback
    def _sync_ms220_optional_alarms() -> None:
        to_add: list[MerossBLEBinarySensor] = []
        for description in MS220_OPTIONAL_ALARM_SENSORS:
            unique_id = f"{coordinator.base_unique_id}-{description.key}"
            entity_id = registry.async_get_entity_id(
                Platform.BINARY_SENSOR, entry.domain, unique_id
            )
            enabled = ms220_alarm_feature_enabled(
                description.key, coordinator.device.data
            )
            if enabled is not None:
                if enabled:
                    if description.key not in added_alarms:
                        to_add.append(MerossBLEBinarySensor(coordinator, description))
                        added_alarms.add(description.key)
                elif entity_id is not None:
                    registry.async_remove(entity_id)
                    added_alarms.discard(description.key)
                continue
            if description.key in added_alarms:
                continue
            if entity_id is not None:
                to_add.append(MerossBLEBinarySensor(coordinator, description))
                added_alarms.add(description.key)
                continue
            if coordinator.device.data.get(description.value_key) is not True:
                continue
            to_add.append(MerossBLEBinarySensor(coordinator, description))
            added_alarms.add(description.key)
        if to_add:
            async_add_entities(to_add)

    entry.async_on_unload(coordinator.async_add_listener(_sync_ms220_optional_alarms))
    _sync_ms220_optional_alarms()


class MerossBLEBinarySensor(MerossBLEEntity, BinarySensorEntity):
    """Meross BLE binary sensor."""

    entity_description: MerossBLEBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MerossBLEDataUpdateCoordinator,
        description: MerossBLEBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.base_unique_id}-{description.key}"

    @property
    def is_on(self) -> bool | None:
        if self.entity_description.key == "battery_low":
            battery = self.parsed_data.get("battery")
            if not isinstance(battery, (int, float)):
                return None
            return battery <= BATTERY_LOW_THRESHOLD

        value = self.parsed_data.get(self.entity_description.value_key)
        if value is None:
            return None
        return bool(value)


class MerossBLEConnectivitySensor(MerossBLEEntity, BinarySensorEntity):
    """True while BLE advertisements are being received."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "connectivity"

    def __init__(self, coordinator: MerossBLEDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}-connectivity"

    @property
    def is_on(self) -> bool:
        return self.coordinator.available
