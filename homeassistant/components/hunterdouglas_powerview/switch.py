"""Switches for Hunter Douglas Powerview advanced features."""

import logging
from typing import Any, override

from aiopvapi.helpers.constants import ATTR_NAME, FUNCTION_SCHEDULE
from aiopvapi.resources.automation import Automation

from homeassistant.components.switch import SwitchEntity
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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerviewConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the hunter douglas advanced feature buttons."""
    pv_entry = entry.runtime_data
    entities: list[SwitchEntity] = []
    for automation in pv_entry.automation_data.values():
        if automation.is_supported(FUNCTION_SCHEDULE):
            scene = pv_entry.scene_data[automation.scene_id]
            room_name = ", ".join(
                getattr(pv_entry.room_data.get(room_id), ATTR_NAME, "")
                for room_id in scene.room_id
            )

            entities.append(
                PowerViewScheduleSwitch(
                    pv_entry.coordinator,
                    pv_entry.device_info,
                    room_name,
                    automation,
                )
            )
    async_add_entities(entities)


class PowerViewScheduleSwitch(HDEntity, SwitchEntity):
    """Representation of a PowerView scheduled event."""

    _attr_translation_key = "schedule"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        automation: Automation,
    ) -> None:
        """Initialize the schedule switch."""
        super().__init__(coordinator, device_info, room_name, str(automation.id))
        self._automation = automation
        self._attr_translation_placeholders = {"schedule_name": str(automation.name)}
        self._attr_extra_state_attributes = {
            STATE_ATTRIBUTE_ROOM_NAME: room_name,
            STATE_ATTRIBUTE_EXECUTION_TIME: automation.get_execution_time(),
            STATE_ATTRIBUTE_EXECUTION_DAYS: automation.get_execution_days(),
        }

    @property
    @override
    def is_on(self) -> bool:
        """Return True if the schedule is enabled."""
        return self._automation.enabled

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the schedule."""
        await self._automation.set_state(True)
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the schedule."""
        await self._automation.set_state(False)
        self.async_write_ha_state()

    @override
    async def async_update(self) -> None:
        """Refresh automation state."""
        async with self.coordinator.radio_operation_lock:
            await self._automation.refresh()
        self.async_write_ha_state()
