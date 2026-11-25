"""Support for Powerview scenes from a Powerview hub."""

import logging
from typing import Any, override

from aiopvapi.helpers.constants import ATTR_NAME
from aiopvapi.resources.scene import Scene as PvScene

from homeassistant.components.scene import Scene
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
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
        room_name = ", ".join(
            getattr(pv_entry.room_data.get(room_id), ATTR_NAME, "")
            for room_id in scene.room_id
        )
        pvscenes.append(
            PowerViewScene(pv_entry.coordinator, pv_entry.device_info, room_name, scene)
        )
    async_remove_stale_scenes(hass, entry, pvscenes)
    async_add_entities(pvscenes)


@callback
def async_remove_stale_scenes(
    hass: HomeAssistant, entry: PowerviewConfigEntry, scenes: list[PowerViewScene]
) -> None:
    """Remove registered scenes that the hub no longer reports."""
    current_unique_ids = {scene.unique_id for scene in scenes}
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if (
            entity_entry.domain == Platform.SCENE
            and entity_entry.unique_id not in current_unique_ids
        ):
            entity_registry.async_remove(entity_entry.entity_id)


class PowerViewScene(HDEntity, Scene):
    """Representation of a Powerview scene."""

    _attr_icon = "mdi:blinds"

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        scene: PvScene,
    ) -> None:
        """Initialize the scene."""
        super().__init__(coordinator, device_info, room_name, scene.id)
        self._scene: PvScene = scene
        self._attr_name = scene.name
        self._attr_extra_state_attributes = {STATE_ATTRIBUTE_ROOM_NAME: room_name}

    @override
    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene. Try to get entities into requested state."""
        shades = await self._scene.activate()
        _LOGGER.debug("Scene activated for shade(s) %s", shades)
