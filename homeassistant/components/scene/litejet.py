"""A single LiteJet scene."""
import logging
import homeassistant.components.litejet as litejet
from homeassistant.components.scene import Scene

DEPENDENCIES = ['litejet']

ATTR_NUMBER = 'number'

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup scenes for the LiteJet platform."""
    litejet_ = litejet.CONNECTION

    add_devices(LiteJetScene(litejet_, i) for i in litejet_.scenes())


class LiteJetScene(Scene):
    """Represents a single LiteJet scene."""

    def __init__(self, lj, i):
        self._lj = lj
        self._index = i
        self._on = False

        self._name = "LiteJet "+str(i)+" "+lj.get_scene_name(i)

    @property
    def name(self):
        return self._name

    @property
    def should_poll(self):
        return False

    @property
    def device_state_attributes(self):
        return {
            ATTR_NUMBER: self._index
        }
 
    def activate(self, **kwargs):
        self._lj.activate_scene(self._index)
        self._on = True
