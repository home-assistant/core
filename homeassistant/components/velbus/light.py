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
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    entities = []
    for channel in cntrl.get_all("light"):
        entities.append(VelbusLight(channel, False))
    for channel in cntrl.get_all("led"):
        entities.append(VelbusLight(channel, True))
    async_add_entities(entities)


class VelbusLight(VelbusEntity, LightEntity):
    """Representation of a Velbus light."""

    def __init__(self, channel, led):
        """Initialize a light Velbus entity."""
        super().__init__(channel)
        self._is_led = led

    @property
    def name(self):
        """Return the display name of this entity."""
        if self._is_led:
            return f"LED {self._channel.get_name()}"
        return self._channel.get_name()

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._is_led:
            return SUPPORT_FLASH
        return SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION

    @property
    def is_on(self):
        """Return true if the light is on."""
        return self._channel.is_on()

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return int((self._channel.get_dimmer_state() * 255) / 100)

    async def async_turn_on(self, **kwargs):
        """Instruct the Velbus light to turn on."""
        if self._is_led:
            if ATTR_FLASH in kwargs:
                if kwargs[ATTR_FLASH] == FLASH_LONG:
                    attr, *args = "set_led_state", "slow"
                elif kwargs[ATTR_FLASH] == FLASH_SHORT:
                    attr, *args = "set_led_state", "fast"
                else:
                    attr, *args = "set_led_state", "on"
            else:
                attr, *args = "set_led_state", "on"
        else:
            if ATTR_BRIGHTNESS in kwargs:
                # Make sure a low but non-zero value is not rounded down to zero
                if kwargs[ATTR_BRIGHTNESS] == 0:
                    brightness = 0
                else:
                    brightness = max(int((kwargs[ATTR_BRIGHTNESS] * 100) / 255), 1)
                attr, *args = (
                    "set_dimmer_state",
                    brightness,
                    kwargs.get(ATTR_TRANSITION, 0),
                )
            else:
                attr, *args = (
                    "restore_dimmer_state",
                    kwargs.get(ATTR_TRANSITION, 0),
                )
        await getattr(self._channel, attr)(*args)

    async def async_turn_off(self, **kwargs):
        """Instruct the velbus light to turn off."""
        if self._is_led:
            attr, *args = "set_led_state", "off"
        else:
            attr, *args = (
                "set_dimmer_state",
                0,
                kwargs.get(ATTR_TRANSITION, 0),
            )
        await getattr(self._channel, attr)(*args)
