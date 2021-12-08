"""Support for deCONZ scenes."""

from __future__ import annotations

from collections.abc import ValuesView
from typing import Any

from pydeconz.group import DeconzScene as PydeconzScene

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .gateway import DeconzGateway, get_gateway_from_config_entry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scenes for deCONZ component."""
    gateway = get_gateway_from_config_entry(hass, config_entry)

    @callback
    def async_add_scene(
        scenes: list[PydeconzScene]
        | ValuesView[PydeconzScene] = gateway.api.scenes.values(),
    ) -> None:
        """Add scene from deCONZ."""
        entities = [DeconzScene(scene, gateway) for scene in scenes]

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            gateway.signal_new_scene,
            async_add_scene,
        )
    )

    async_add_scene()


class DeconzScene(Scene):
    """Representation of a deCONZ scene."""

    def __init__(self, scene: PydeconzScene, gateway: DeconzGateway) -> None:
        """Set up a scene."""
        self._scene = scene
        self.gateway = gateway

        self._attr_name = scene.full_name

    async def async_added_to_hass(self) -> None:
        """Subscribe to sensors events."""
        self.gateway.deconz_ids[self.entity_id] = self._scene.deconz_id

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect scene object when removed."""
        del self.gateway.deconz_ids[self.entity_id]
        self._scene = None

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._scene.recall()
