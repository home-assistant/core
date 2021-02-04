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
    """Set up SmartHab lights from a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id][DATA_HUB]

    entities = (
        SmartHabLight(light)
        for light in await hub.async_get_device_list()
        if isinstance(light, pysmarthab.Light)
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

    async def async_turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        await self._light.async_turn_on()

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self._light.async_turn_off()

    async def async_update(self):
        """Fetch new state data for this light."""
        try:
            await self._light.async_update()
        except Timeout:
            _LOGGER.error(
                "Reached timeout while updating light %s from API", self.entity_id
            )
