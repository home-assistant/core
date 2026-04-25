"""Sensor platform for the UniFi Access integration."""

from __future__ import annotations

from datetime import UTC, datetime

from unifi_access_api import Door, DoorLockRuleType

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import UnifiAccessConfigEntry, UnifiAccessCoordinator
from .entity import UnifiAccessEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnifiAccessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UniFi Access sensor entities."""
    coordinator = entry.runtime_data
    added_doors: set[str] = set()

    @callback
    def _async_add_lock_rule_sensors() -> None:
        new_door_ids = sorted(coordinator.get_lock_rule_sensor_door_ids() - added_doors)
        if not new_door_ids:
            return

        async_add_entities(
            sensor_class(coordinator, coordinator.data.doors[door_id])
            for door_id in new_door_ids
            if door_id in coordinator.data.doors
            for sensor_class in (
                UnifiAccessDoorLockRuleSensor,
                UnifiAccessDoorLockRuleEndTimeSensor,
            )
        )
        added_doors.update(new_door_ids)

    _async_add_lock_rule_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_lock_rule_sensors))


class UnifiAccessDoorLockRuleSensor(UnifiAccessEntity, SensorEntity):
    """Sensor reporting the current lock rule for a UniFi Access door."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = [t.value for t in DoorLockRuleType if t != DoorLockRuleType.NONE]
    _attr_translation_key = "door_lock_rule"

    def __init__(
        self,
        coordinator: UnifiAccessCoordinator,
        door: Door,
    ) -> None:
        """Initialize the lock rule sensor."""
        super().__init__(coordinator, door, "lock_rule")

    @property
    def native_value(self) -> str | None:
        """Return the active lock rule type, or None if no rule is active."""
        rule_status = self.coordinator.get_lock_rule_status(self._door_id)
        if rule_status is None or rule_status.type is DoorLockRuleType.NONE:
            return None
        return rule_status.type.value

    @property
    def available(self) -> bool:
        """Return whether the sensor should currently be shown as available."""
        return super().available and (
            self._door_id in self.coordinator.get_lock_rule_sensor_door_ids()
        )


class UnifiAccessDoorLockRuleEndTimeSensor(UnifiAccessEntity, SensorEntity):
    """Sensor reporting when the current lock rule expires."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "door_lock_rule_ended_time"

    def __init__(
        self,
        coordinator: UnifiAccessCoordinator,
        door: Door,
    ) -> None:
        """Initialize the lock rule end time sensor."""
        super().__init__(coordinator, door, "lock_rule_ended_time")

    @property
    def native_value(self) -> datetime | None:
        """Return the time when the lock rule expires, or None if no rule is active."""
        rule_status = self.coordinator.get_lock_rule_status(self._door_id)
        if rule_status is None or not rule_status.ended_time:
            return None
        return datetime.fromtimestamp(rule_status.ended_time, tz=UTC)

    @property
    def available(self) -> bool:
        """Return whether the sensor should currently be shown as available."""
        return super().available and (
            self._door_id in self.coordinator.get_lock_rule_sensor_door_ids()
        )
