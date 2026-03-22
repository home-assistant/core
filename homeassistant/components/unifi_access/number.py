"""Number platform for the UniFi Access integration."""

from __future__ import annotations

from unifi_access_api import Door

from homeassistant.components.number import NumberDeviceClass, NumberMode, RestoreNumber
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import UnifiAccessConfigEntry, UnifiAccessCoordinator
from .const import DEFAULT_LOCK_RULE_INTERVAL
from .entity import UnifiAccessEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnifiAccessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UniFi Access number entities."""
    coordinator = entry.runtime_data
    if coordinator.data.supports_lock_rules:
        async_add_entities(
            UnifiAccessDoorLockRuleIntervalNumberEntity(coordinator, door)
            for door in coordinator.data.doors.values()
        )


class UnifiAccessDoorLockRuleIntervalNumberEntity(UnifiAccessEntity, RestoreNumber):
    """Number entity for configuring the interval of a custom lock rule.

    The interval (in minutes) is stored locally and used when the user
    selects a 'custom' temporary lock rule via the select entity.
    """

    _attr_device_class = NumberDeviceClass.DURATION
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1
    _attr_native_max_value = 480
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_translation_key = "door_lock_rule_interval"

    def __init__(
        self,
        coordinator: UnifiAccessCoordinator,
        door: Door,
    ) -> None:
        """Initialize the lock rule interval number entity."""
        super().__init__(coordinator, door, "lock_rule_interval")
        self._attr_native_value = float(DEFAULT_LOCK_RULE_INTERVAL)

    async def async_added_to_hass(self) -> None:
        """Restore the last known interval value on startup."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_number_data()
        if last_data and last_data.native_value is not None:
            self._attr_native_value = last_data.native_value
        self.coordinator.lock_rule_intervals[self._door_id] = int(
            self._attr_native_value
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set a new interval value and sync it to the coordinator."""
        self._attr_native_value = value
        self.coordinator.lock_rule_intervals[self._door_id] = int(value)
        self.async_write_ha_state()
