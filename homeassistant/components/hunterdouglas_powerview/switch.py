"""Switches for Hunter Douglas Powerview advanced features."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final, override

from aiopvapi.helpers.constants import ATTR_NAME, FUNCTION_SCHEDULE
from aiopvapi.resources.automation import Automation

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    STATE_ATTRIBUTE_EXECUTION_DAYS,
    STATE_ATTRIBUTE_EXECUTION_TIME,
    STATE_ATTRIBUTE_ROOM_NAME,
)
from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import HDEntity
from .model import PowerviewConfigEntry, PowerviewDeviceInfo


@dataclass(frozen=True, kw_only=True)
class PowerviewSwitchDescription(SwitchEntityDescription):
    """Class to describe a Switch entity."""

    entity_category: EntityCategory = EntityCategory.CONFIG
    fn_create_entity: Callable[[Automation], bool]
    fn_isenabled: Callable[[Automation], bool]
    fn_off: Callable[[Automation], Awaitable[None]]
    fn_on: Callable[[Automation], Awaitable[None]]


SWITCHES: Final = (
    PowerviewSwitchDescription(
        key="schedule",
        translation_key="schedule",
        icon="mdi:calendar-clock",
        fn_create_entity=lambda automation: automation.is_supported(FUNCTION_SCHEDULE),
        fn_isenabled=lambda automation: automation.enabled,
        fn_off=lambda automation: automation.set_state(False),
        fn_on=lambda automation: automation.set_state(True),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerviewConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the hunter douglas advanced feature switches."""
    pv_entry = entry.runtime_data
    entities: list[SwitchEntity] = []
    for automation in pv_entry.automation_data.values():
        scene = pv_entry.scene_data[automation.scene_id]
        room_name = ", ".join(
            getattr(pv_entry.room_data.get(room_id), ATTR_NAME, "")
            for room_id in scene.room_id
        )
        entities.extend(
            PowerViewSwitch(
                pv_entry.coordinator,
                pv_entry.device_info,
                room_name,
                automation,
                description,
            )
            for description in SWITCHES
            if description.fn_create_entity(automation)
        )
    async_add_entities(entities)


class PowerViewSwitch(HDEntity, SwitchEntity):
    """Representation of a PowerView scheduled event."""

    entity_description: PowerviewSwitchDescription

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        automation: Automation,
        description: PowerviewSwitchDescription,
    ) -> None:
        """Initialize the schedule switch."""
        super().__init__(coordinator, device_info, room_name, str(automation.id))
        self._automation: Automation = automation
        self._attr_translation_placeholders = {"schedule_name": str(automation.name)}
        self._attr_extra_state_attributes = {
            STATE_ATTRIBUTE_ROOM_NAME: room_name,
            STATE_ATTRIBUTE_EXECUTION_TIME: automation.get_execution_time(),
            STATE_ATTRIBUTE_EXECUTION_DAYS: automation.get_execution_days(),
        }
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool:
        """Return True if the schedule is enabled."""
        return self.entity_description.fn_isenabled(self._automation)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the schedule."""
        async with self.coordinator.radio_operation_lock:
            await self.entity_description.fn_on(self._automation)
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the schedule."""
        async with self.coordinator.radio_operation_lock:
            await self.entity_description.fn_off(self._automation)
        self.async_write_ha_state()

    @override
    async def async_update(self) -> None:
        """Refresh automation state."""
        async with self.coordinator.radio_operation_lock:
            await self._automation.refresh()
        self.async_write_ha_state()
