"""Support for Powerview scenes from a Powerview hub."""
from __future__ import annotations

import logging
from typing import Any

from aiopvapi.helpers.constants import ATTR_NAME
from aiopvapi.resources.scene import Scene as PvScene

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, STATE_ATTRIBUTE_ROOM_NAME
from .coordinator import PowerviewShadeUpdateCoordinator
from .entity import HDEntity
from .model import PowerviewDeviceInfo, PowerviewEntryData

_LOGGER = logging.getLogger(__name__)

RESYNC_DELAY = 60


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up powerview scene entries."""

    pv_entry: PowerviewEntryData = hass.data[DOMAIN][entry.entry_id]

    pvscenes: list[PowerViewScene] = []
    for scene in pv_entry.scene_data.values():
        room_name = getattr(pv_entry.room_data.get(scene.room_id), ATTR_NAME, "")
        pvscenes.append(
            PowerViewScene(pv_entry.coordinator, pv_entry.device_info, room_name, scene)
        )
    async_add_entities(pvscenes)


class PowerViewScene(HDEntity, Scene):
    """Representation of a Powerview scene."""

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
        self._forced_resync: list = []

    @property
    def name(self) -> str:
        """Return the name of the scene."""
        return self._scene.name

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        return {STATE_ATTRIBUTE_ROOM_NAME: self._room_name}

    @property
    def icon(self) -> str:
        """Icon to use in the frontend."""
        return "mdi:blinds"

    async def _async_force_resync(self, *_: Any) -> None:
        """Force a resync after an update since the hub may have stale state."""
        for shade_id in self._forced_resync:
            _LOGGER.debug("Force resync of shade %s", self.name)
            await self.data.get_shade(shade_id=shade_id).refresh()
        self._forced_resync = []

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene. Try to get entities into requested state."""
        shades = await self._scene.activate()
        _LOGGER.debug("Scene activated for shade(s) %s", shades)
        self._forced_resync = shades
        async_call_later(self.hass, RESYNC_DELAY, self._async_force_resync)
