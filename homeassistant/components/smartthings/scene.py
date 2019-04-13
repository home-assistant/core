"""Support for scenes through the SmartThings cloud API."""
from homeassistant.components.scene import Scene

from .const import DATA_BROKERS, DOMAIN


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Platform uses config entry setup."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add switches for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    async_add_entities(
        [SmartThingsScene(scene) for scene in broker.scenes.values()])


class SmartThingsScene(Scene):
    """Define a SmartThings scene."""

    def __init__(self, scene):
        """Init the scene class."""
        self._scene = scene

    async def async_activate(self):
        """Activate scene."""
        await self._scene.execute()

    @property
    def device_state_attributes(self):
        """Get attributes about the state."""
        return {
            'icon': self._scene.icon,
            'color': self._scene.color,
            'location_id': self._scene.location_id
        }

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._scene.name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._scene.scene_id
