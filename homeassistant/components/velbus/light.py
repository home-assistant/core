"""Support for Velbus light dimmers."""
import logging

from velbus.util import VelbusException

from homeassistant.components.light import (
    Light,
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_TRANSITION,
)

from . import VelbusEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Velbus light based on config_entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    modules_data = hass.data[DOMAIN][entry.entry_id]["light"]
    entities = []
    for address, channel in modules_data:
        module = cntrl.get_module(address)
        entities.append(VelbusDimmer(module, channel))
    async_add_entities(entities)


class VelbusDimmer(VelbusEntity, Light):
    """Representation of a light dimmer."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION

    @property
    def is_on(self):
        """Return true if the dimmer is on."""
        return self._module.is_on(self._channel)

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._module.get_dimmer_state(self._channel)

    def turn_on(self, **kwargs):
        """Instruct the Velbus dimmer to set requested brightness level."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])
        else:
            brightness = 0
        if ATTR_TRANSITION in kwargs:
            transitiontime = int(kwargs[ATTR_TRANSITION])
        else:
            transitiontime = 0

        try:
            if ATTR_BRIGHTNESS in kwargs:
                self._module.set_dimmer_state(
                    self._channel,
                    brightness,
                    transitiontime,
                    self.async_schedule_update_ha_state(False),
                )
            else:
                self._module.restore_dimmer_state(
                    self._channel,
                    transitiontime,
                    self.async_schedule_update_ha_state(),
                )
        except VelbusException as err:
            _LOGGER.error("A Velbus error occurred: %s", err)

    def turn_off(self, **kwargs):
        """Instruct the velbus dimmer to turn off."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])
        else:
            brightness = 0
        if ATTR_TRANSITION in kwargs:
            transitiontime = int(kwargs[ATTR_TRANSITION])
        else:
            transitiontime = 0

        try:
            self._module.set_dimmer_state(
                self._channel,
                brightness,
                transitiontime,
                self.async_schedule_update_ha_state(False),
            )
        except VelbusException as err:
            _LOGGER.error("A Velbus error occurred: %s", err)
