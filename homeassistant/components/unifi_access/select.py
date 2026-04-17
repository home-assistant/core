"""Select platform for the UniFi Access integration."""

from __future__ import annotations

from unifi_access_api import Door, DoorLockRuleType, UnifiAccessError

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
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
    added_doors: set[str] = set()

    @callback
    def _async_add_lock_rule_selects() -> None:
        new_door_ids = sorted(coordinator.get_lock_rule_sensor_door_ids() - added_doors)
        if not new_door_ids:
            return

        async_add_entities(
            UnifiAccessDoorLockRuleSelectEntity(
                coordinator, coordinator.data.doors[door_id]
            )
            for door_id in new_door_ids
            if door_id in coordinator.data.doors
        )
        added_doors.update(new_door_ids)

    _async_add_lock_rule_selects()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_lock_rule_selects))


class UnifiAccessDoorLockRuleSelectEntity(UnifiAccessEntity, SelectEntity):
    """Select entity for choosing the active temporary lock rule on a door."""

    _attr_translation_key = "door_lock_rule"

    def __init__(
        self,
        coordinator: UnifiAccessCoordinator,
        door: Door,
    ) -> None:
        """Initialize the door lock rule select entity."""
        super().__init__(coordinator, door, "lock_rule_select")

    @property
    def current_option(self) -> str | None:
        """Return the currently active lock rule, or None if no rule is set."""
        rule_status = self.coordinator.get_lock_rule_status(self._door_id)
        if rule_status is None or rule_status.type in (
            DoorLockRuleType.NONE,
            DoorLockRuleType.RESET,
            DoorLockRuleType.LOCK_NOW,
        ):
            return None
        value = rule_status.type.value
        return value if value in self.options else None

    @property
    def options(self) -> list[str]:
        """Return the available lock rule options."""
        opts = ["keep_lock", "keep_unlock", "custom", "reset"]
        rule_status = self.coordinator.get_lock_rule_status(self._door_id)
        if rule_status is not None and rule_status.type in (
            DoorLockRuleType.SCHEDULE,
            DoorLockRuleType.LOCK_EARLY,
        ):
            opts.extend(["schedule", "lock_early"])
        return opts

    @property
    def available(self) -> bool:
        """Return whether the select should currently be shown as available."""
        return super().available and (
            self._door_id in self.coordinator.get_lock_rule_sensor_door_ids()
        )

    async def async_select_option(self, option: str) -> None:
        """Apply the selected lock rule to the door."""
        if option == DoorLockRuleType.SCHEDULE.value:
            return
        try:
            await self.coordinator.async_set_lock_rule(self._door_id, option)
        except UnifiAccessError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="lock_rule_failed",
            ) from err
