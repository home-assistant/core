"""Support for KNX scenes."""
import voluptuous as vol

from homeassistant.components.scene import CONF_PLATFORM, Scene
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import ATTR_DISCOVER_DEVICES, DATA_KNX

CONF_SCENE_NUMBER = 'scene_number'

DEFAULT_NAME = 'KNX SCENE'
DEPENDENCIES = ['knx']

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'knx',
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Required(CONF_SCENE_NUMBER): cv.positive_int,
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the scenes for KNX platform."""
    if discovery_info is not None:
        async_add_entities_discovery(hass, discovery_info, async_add_entities)
    else:
        async_add_entities_config(hass, config, async_add_entities)


@callback
def async_add_entities_discovery(hass, discovery_info, async_add_entities):
    """Set up scenes for KNX platform configured via xknx.yaml."""
    entities = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        entities.append(KNXScene(device))
    async_add_entities(entities)


@callback
def async_add_entities_config(hass, config, async_add_entities):
    """Set up scene for KNX platform configured within platform."""
    import xknx
    scene = xknx.devices.Scene(
        hass.data[DATA_KNX].xknx,
        name=config.get(CONF_NAME),
        group_address=config.get(CONF_ADDRESS),
        scene_number=config.get(CONF_SCENE_NUMBER))
    hass.data[DATA_KNX].xknx.devices.add(scene)
    async_add_entities([KNXScene(scene)])


class KNXScene(Scene):
    """Representation of a KNX scene."""

    def __init__(self, scene):
        """Init KNX scene."""
        self.scene = scene

    @property
    def name(self):
        """Return the name of the scene."""
        return self.scene.name

    async def async_activate(self):
        """Activate the scene."""
        await self.scene.run()
