"""Support for Hunter Douglas PowerView scheduled events."""

from __future__ import annotations

import logging
from typing import Any

from aiopvapi.helpers.constants import ATTR_NAME
from aiopvapi.resources.automation import Automation

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, STATE_ATTRIBUTE_ROOM_NAME
from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import HDEntity
from .model import PowerviewConfigEntry, PowerviewDeviceInfo

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerviewConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PowerView schedule switches."""
    pv_entry = entry.runtime_data

    # Count automations per scene to determine if an index suffix is needed
    scene_automation_counts: dict = {}
    for automation in pv_entry.automation_data.values():
        key = automation.scene_id
        scene_automation_counts[key] = scene_automation_counts.get(key, 0) + 1

    scene_automation_index: dict = {}
    entities: list[PowerViewScheduleSwitch] = []

    for automation in sorted(pv_entry.automation_data.values(), key=lambda a: a.id):
        key = automation.scene_id
        scene = pv_entry.scene_data.get(key)
        scene_name = scene.name if scene is not None else str(key)
        room_name = getattr(
            pv_entry.room_data.get(getattr(scene, "room_id", None)), ATTR_NAME, ""
        )

        scene_automation_index[key] = scene_automation_index.get(key, 0) + 1
        schedule_index = (
            scene_automation_index[key]
            if scene_automation_counts[key] > 1
            else None
        )

        entities.append(
            PowerViewScheduleSwitch(
                pv_entry.coordinator,
                pv_entry.device_info,
                room_name,
                automation,
                scene_name,
                schedule_index,
            )
        )

    async_add_entities(entities)


class PowerViewScheduleSwitch(HDEntity, SwitchEntity):
    """Representation of a PowerView scheduled event."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        automation: Automation,
        scene_name: str,
        schedule_index: int | None,
    ) -> None:
        """Initialize the schedule switch."""
        super().__init__(coordinator, device_info, room_name, str(automation.id))
        self._automation = automation
        name = f"{scene_name} Schedule"
        if schedule_index is not None:
            name = f"{name} {schedule_index}"
        self._attr_name = name
        self._attr_extra_state_attributes = {
            STATE_ATTRIBUTE_ROOM_NAME: room_name,
            "scene_name": scene_name,
            "scene_id": automation.scene_id,
            "scene_entity_id": None,
            "execution_time": automation.get_execution_time(),
            "execution_days": automation.get_execution_days(),
        }

    async def async_added_to_hass(self) -> None:
        """Resolve scene PowerView ID to HA entity ID once registered."""
        await super().async_added_to_hass()
        entity_registry = er.async_get(self.hass)
        serial = self._device_info.serial_number
        entity_id = entity_registry.async_get_entity_id(
            Platform.SCENE, DOMAIN, f"{serial}_{self._automation.scene_id}"
        )
        if entity_id:
            self._attr_extra_state_attributes = {
                **self._attr_extra_state_attributes,
                "scene_entity_id": entity_id,
            }
            self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return True if the schedule is enabled."""
        return self._automation.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the schedule."""
        await self._automation.set_state(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the schedule."""
        await self._automation.set_state(False)
        self.async_write_ha_state()
