"""Support for SmartHab device integration."""
from datetime import timedelta
import logging

import pysmarthab
from requests.exceptions import Timeout

from homeassistant.components.light import Light

from . import DATA_HUB, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the SmartHab lights platform."""

    hub = hass.data[DOMAIN][DATA_HUB]
    devices = hub.get_device_list()

    _LOGGER.debug("Found a total of %s devices", str(len(devices)))

    entities = (
        SmartHabLight(light) for light in devices if isinstance(light, pysmarthab.Light)
    )

    add_entities(entities, True)


class SmartHabLight(Light):
    """Representation of a SmartHab Light."""

    def __init__(self, light):
        """Initialize a SmartHabLight."""
        self._light = light

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._light.device_id

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._light.label

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._light.state

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        self._light.turn_on()

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._light.turn_off()

    def update(self):
        """Fetch new state data for this light."""
        try:
            self._light.update()
        except Timeout:
            _LOGGER.error(
                "Reached timeout while updating light %s from API", self.entity_id
            )
