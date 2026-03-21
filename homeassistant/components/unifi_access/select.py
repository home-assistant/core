"""Select platform for the UniFi Access integration."""

from __future__ import annotations

from unifi_access_api import Door, DoorLockRuleType

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import UnifiAccessConfigEntry, UnifiAccessCoordinator
from .entity import UnifiAccessEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnifiAccessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UniFi Access select entities."""
    coordinator = entry.runtime_data
    if coordinator.data.supports_lock_rules:
        async_add_entities(
            UnifiAccessDoorLockRuleSelectEntity(coordinator, door)
            for door in coordinator.data.doors.values()
        )


class UnifiAccessDoorLockRuleSelectEntity(UnifiAccessEntity, SelectEntity):
    """Select entity for choosing the active temporary lock rule on a door."""

    _attr_translation_key = "door_lock_rules"

    def __init__(
        self,
        coordinator: UnifiAccessCoordinator,
        door: Door,
    ) -> None:
        """Initialize the door lock rule select entity."""
        super().__init__(coordinator, door, "lock_rule_select")

    @property
    def current_option(self) -> str | None:
        """Return the currently active lock rule, or None/empty if no rule is set."""
        rule_status = self._door.lock_rule_status
        if rule_status is None or rule_status.type in (
            DoorLockRuleType.NONE,
            DoorLockRuleType.RESET,
        ):
            return ""
        return rule_status.type.value

    @property
    def options(self) -> list[str]:
        """Return the available lock rule options."""
        opts = ["", "keep_lock", "keep_unlock", "custom", "reset"]
        if self.current_option == DoorLockRuleType.SCHEDULE:
            opts.append("lock_early")
        return opts

    async def async_select_option(self, option: str) -> None:
        """Apply the selected lock rule to the door."""
        if not option:
            return
        await self.coordinator.async_set_lock_rule(self._door_id, option)
