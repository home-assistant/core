"""Support for Powerview scenes from a Powerview hub."""

from __future__ import annotations

import logging
from typing import Any

from aiopvapi.helpers.constants import ATTR_NAME
from aiopvapi.resources.scene import Scene as PvScene

from homeassistant.components.scene import Scene
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import STATE_ATTRIBUTE_ROOM_NAME
from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import HDEntity
from .model import PowerviewConfigEntry, PowerviewDeviceInfo

_LOGGER = logging.getLogger(__name__)

RESYNC_DELAY = 60


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerviewConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up powerview scene entries."""
    pv_entry = entry.runtime_data
    pvscenes: list[PowerViewScene] = []
    for scene in pv_entry.scene_data.values():
        room_name = getattr(pv_entry.room_data.get(scene.room_id), ATTR_NAME, "")
        pvscenes.append(
            PowerViewScene(
                pv_entry.coordinator,
                pv_entry.device_info,
                room_name,
                scene,
                pv_entry.scene_to_shade_ids.get(scene.id, []),
            )
        )
    async_add_entities(pvscenes)


class PowerViewScene(HDEntity, Scene):
    """Representation of a Powerview scene."""

    _attr_icon = "mdi:blinds"

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        scene: PvScene,
        shade_ids: list[int],
    ) -> None:
        """Initialize the scene."""
        super().__init__(coordinator, device_info, room_name, scene.id)
        self._scene: PvScene = scene
        self._shade_ids = shade_ids
        self._attr_name = scene.name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return state attributes, resolving cross-platform entity IDs dynamically."""
        entity_registry = er.async_get(self.hass)
        config_entry_id = self.coordinator.config_entry.entry_id
        all_entries = er.async_entries_for_config_entry(
            entity_registry, config_entry_id
        )
        serial = self._device_info.serial_number

        shade_entity_ids: list[str] = []
        for shade_id in self._shade_ids:
            prefix = f"{serial}_{shade_id}"
            shade_entity_ids.extend(
                e.entity_id
                for e in all_entries
                if e.domain == Platform.COVER
                and (e.unique_id == prefix or e.unique_id.startswith(f"{prefix}_"))
            )

        return {
            STATE_ATTRIBUTE_ROOM_NAME: self._room_name,
            "shade_ids": self._shade_ids,
            "shade_entity_ids": shade_entity_ids,
        }

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene. Try to get entities into requested state."""
        shades = await self._scene.activate()
        _LOGGER.debug("Scene activated for shade(s) %s", shades)
