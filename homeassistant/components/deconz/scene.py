"""Support for deCONZ scenes."""

from __future__ import annotations

from typing import Any

from pydeconz.models.event import EventType

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import DeconzSceneMixin
from .hub import DeconzHub


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scenes for deCONZ integration."""
    hub = DeconzHub.get_hub(hass, config_entry)
    hub.entities[SCENE_DOMAIN] = set()

    @callback
    def async_add_scene(_: EventType, scene_id: str) -> None:
        """Add scene from deCONZ."""
        scene = hub.api.scenes[scene_id]
        async_add_entities([DeconzScene(scene, hub)])

    hub.register_platform_add_device_callback(
        async_add_scene,
        hub.api.scenes,
    )


class DeconzScene(DeconzSceneMixin, Scene):
    """Representation of a deCONZ scene."""

    TYPE = SCENE_DOMAIN

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self.hub.api.scenes.recall(
            self._device.group_id,
            self._device.id,
        )
