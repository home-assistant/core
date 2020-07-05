"""Support for LiteJet scenes."""
import logging
from typing import Any

from homeassistant.components import litejet
from homeassistant.components.scene import Scene

ATTR_NUMBER = "number"

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up scenes for the LiteJet platform."""
    litejet_ = hass.data["litejet_system"]

    devices = []
    for i in litejet_.scenes():
        name = litejet_.get_scene_name(i)
        if not litejet.is_ignored(hass, name):
            devices.append(LiteJetScene(litejet_, i, name))
    add_entities(devices)


class LiteJetScene(Scene):
    """Representation of a single LiteJet scene."""

    def __init__(self, lj, i, name):
        """Initialize the scene."""
        self._lj = lj
        self._index = i
        self._name = name

    @property
    def name(self):
        """Return the name of the scene."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the device-specific state attributes."""
        return {ATTR_NUMBER: self._index}

    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self._lj.activate_scene(self._index)
