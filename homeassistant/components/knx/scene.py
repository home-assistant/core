"""Support for KNX scenes."""
from typing import Any

from xknx.devices import Scene as XknxScene

from homeassistant.components.scene import Scene
from homeassistant.core import callback

from . import ATTR_DISCOVER_DEVICES, DATA_KNX


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the scenes for KNX platform."""
    if discovery_info is not None:
        async_add_entities_discovery(hass, discovery_info, async_add_entities)


@callback
def async_add_entities_discovery(hass, discovery_info, async_add_entities):
    """Set up scenes for KNX platform configured via xknx.yaml."""
    entities = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        entities.append(KNXScene(device))
    async_add_entities(entities)


class KNXScene(Scene):
    """Representation of a KNX scene."""

    def __init__(self, scene: XknxScene):
        """Init KNX scene."""
        self.scene = scene

    @property
    def name(self):
        """Return the name of the scene."""
        return self.scene.name

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self.scene.run()
