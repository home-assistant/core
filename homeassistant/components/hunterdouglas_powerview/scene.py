"""Support for Powerview scenes from a Powerview hub."""

from __future__ import annotations

import logging
from typing import Any

from aiopvapi.helpers.constants import ATTR_NAME
from aiopvapi.resources.scene import Scene as PvScene

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import STATE_ATTRIBUTE_ROOM_NAME
from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import HDEntity
from .model import PowerviewConfigEntry, PowerviewDeviceInfo

_LOGGER = logging.getLogger(__name__)

RESYNC_DELAY = 60


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerviewConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up powerview scene entries."""
    pv_entry = entry.runtime_data
    pvscenes: list[PowerViewScene] = []
    for scene in pv_entry.scene_data.values():
        room_name = getattr(pv_entry.room_data.get(scene.room_id), ATTR_NAME, "")
        pvscenes.append(
            PowerViewScene(pv_entry.coordinator, pv_entry.device_info, room_name, scene)
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
    ) -> None:
        """Initialize the scene."""
        super().__init__(coordinator, device_info, room_name, scene.id)
        self._scene: PvScene = scene
        self._attr_name = scene.name
        self._attr_extra_state_attributes = {STATE_ATTRIBUTE_ROOM_NAME: room_name}

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene. Try to get entities into requested state."""
        shades = await self._scene.activate()
        _LOGGER.debug("Scene activated for shade(s) %s", shades)
