"""Support for deCONZ scenes."""
from homeassistant.components.scene import Scene
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import NEW_SCENE
from .gateway import get_gateway_from_config_entry


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up deCONZ scenes."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up scenes for deCONZ component."""
    gateway = get_gateway_from_config_entry(hass, config_entry)

    @callback
    def async_add_scene(scenes):
        """Add scene from deCONZ."""
        entities = []

        for scene in scenes:
            entities.append(DeconzScene(scene, gateway))

        async_add_entities(entities)

    gateway.listeners.append(async_dispatcher_connect(
        hass, gateway.async_event_new_device(NEW_SCENE), async_add_scene))

    async_add_scene(gateway.api.scenes.values())


class DeconzScene(Scene):
    """Representation of a deCONZ scene."""

    def __init__(self, scene, gateway):
        """Set up a scene."""
        self._scene = scene
        self.gateway = gateway

    async def async_added_to_hass(self):
        """Subscribe to sensors events."""
        self.gateway.deconz_ids[self.entity_id] = self._scene.deconz_id

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect scene object when removed."""
        self._scene = None

    async def async_activate(self):
        """Activate the scene."""
        await self._scene.async_set_state({})

    @property
    def name(self):
        """Return the name of the scene."""
        return self._scene.full_name
