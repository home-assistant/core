"""Support for deCONZ scenes."""
from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import NEW_SCENE
from .gateway import get_gateway_from_config_entry


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up scenes for deCONZ component."""
    gateway = get_gateway_from_config_entry(hass, config_entry)

    @callback
    def async_add_scene(scenes=gateway.api.scenes.values()):
        """Add scene from deCONZ."""
        entities = [DeconzScene(scene, gateway) for scene in scenes]

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, gateway.async_signal_new_device(NEW_SCENE), async_add_scene
        )
    )

    async_add_scene()


class DeconzScene(Scene):
    """Representation of a deCONZ scene."""

    def __init__(self, scene, gateway):
        """Set up a scene."""
        self._scene = scene
        self.gateway = gateway

        self._attr_name = scene.full_name

    async def async_added_to_hass(self):
        """Subscribe to sensors events."""
        self.gateway.deconz_ids[self.entity_id] = self._scene.deconz_id

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect scene object when removed."""
        del self.gateway.deconz_ids[self.entity_id]
        self._scene = None

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._scene.recall()
