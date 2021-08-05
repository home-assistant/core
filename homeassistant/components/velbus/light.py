"""Support for Velbus light."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_FLASH,
    ATTR_TRANSITION,
    FLASH_LONG,
    FLASH_SHORT,
    SUPPORT_BRIGHTNESS,
    SUPPORT_FLASH,
    SUPPORT_TRANSITION,
    LightEntity,
)

from . import VelbusEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Velbus switch based on config_entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for channel in cntrl.get_all("climate"):
        entities.append(VelbusLight(channel))
    async_add_entities(entities)


class VelbusLight(VelbusEntity, LightEntity):
    """Representation of a Velbus light."""

    @property
    def name(self):
        """Return the display name of this entity."""
        # if self._module.light_is_buttonled(self._channel):
        #    return f"LED {self._module.get_name(self._channel)}"
        return self._channel.get_name()

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._channel.light_is_buttonled():
            return SUPPORT_FLASH
        return SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION

    @property
    def entity_registry_enabled_default(self):
        """Disable Button LEDs by default."""
        if self._channel.light_is_buttonled():
            return False
        return True

    @property
    def is_on(self):
        """Return true if the light is on."""
        return self._channel.is_on()

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return int((self._channel.get_dimmer_state() * 255) / 100)

    def turn_on(self, **kwargs):
        """Instruct the Velbus light to turn on."""
        if self._module.light_is_buttonled(self._channel):
            if ATTR_FLASH in kwargs:
                if kwargs[ATTR_FLASH] == FLASH_LONG:
                    attr, *args = "set_led_state", self._channel, "slow"
                elif kwargs[ATTR_FLASH] == FLASH_SHORT:
                    attr, *args = "set_led_state", self._channel, "fast"
                else:
                    attr, *args = "set_led_state", self._channel, "on"
            else:
                attr, *args = "set_led_state", self._channel, "on"
        else:
            if ATTR_BRIGHTNESS in kwargs:
                # Make sure a low but non-zero value is not rounded down to zero
                if kwargs[ATTR_BRIGHTNESS] == 0:
                    brightness = 0
                else:
                    brightness = max(int((kwargs[ATTR_BRIGHTNESS] * 100) / 255), 1)
                attr, *args = (
                    "set_dimmer_state",
                    self._channel,
                    brightness,
                    kwargs.get(ATTR_TRANSITION, 0),
                )
            else:
                attr, *args = (
                    "restore_dimmer_state",
                    self._channel,
                    kwargs.get(ATTR_TRANSITION, 0),
                )
        getattr(self._channel, attr)(*args)

    def turn_off(self, **kwargs):
        """Instruct the velbus light to turn off."""
        if self._channel.light_is_buttonled():
            attr, *args = "set_led_state", self._channel, "off"
        else:
            attr, *args = (
                "set_dimmer_state",
                self._channel,
                0,
                kwargs.get(ATTR_TRANSITION, 0),
            )
        getattr(self._channel, attr)(*args)
