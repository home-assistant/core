"""Support for SmartHab device integration."""
from datetime import timedelta
import logging

import pysmarthab
from requests.exceptions import Timeout

from homeassistant.components.light import LightEntity

from . import DATA_HUB, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up SmartHab covers from a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id][DATA_HUB]

    devices = await hass.async_add_executor_job(hub.get_device_list)
    _LOGGER.debug("Found a total of %s devices", str(len(devices)))

    entities = (
        SmartHabLight(light) for light in devices if isinstance(light, pysmarthab.Light)
    )

    async_add_entities(entities, True)


class SmartHabLight(LightEntity):
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
