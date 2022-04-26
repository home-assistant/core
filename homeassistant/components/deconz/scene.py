"""Support for deCONZ scenes."""

from __future__ import annotations

from typing import Any

from pydeconz.models.event import EventType

from homeassistant.components.scene import DOMAIN, Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .deconz_device import DeconzSceneMixin
from .gateway import get_gateway_from_config_entry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scenes for deCONZ integration."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_scene(_: EventType, scene_id: str) -> None:
        """Add scene from deCONZ."""
        scene = gateway.api.scenes[scene_id]
        async_add_entities([DeconzScene(scene, gateway)])

    config_entry.async_on_unload(
        gateway.api.scenes.subscribe(
            async_add_scene,
            EventType.ADDED,
        )
    )

    for scene_id in gateway.api.scenes:
        async_add_scene(EventType.ADDED, scene_id)


class DeconzScene(DeconzSceneMixin, Scene):
    """Representation of a deCONZ scene."""

    TYPE = DOMAIN

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._device.recall()
