"""Platform for UPB light integration."""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_FLASH,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_FLASH,
    SUPPORT_TRANSITION,
    Light,
)
from homeassistant.helpers import entity_platform

from . import UpbAttachedEntity
from .const import DOMAIN, UPB_BLINK_RATE_SCHEMA, UPB_BRIGHTNESS_RATE_SCHEMA

SERVICE_LIGHT_FADE_START = "light_fade_start"
SERVICE_LIGHT_FADE_STOP = "light_fade_stop"
SERVICE_LIGHT_UPDATE_STATUS = "light_update_status"
SERVICE_LIGHT_BLINK = "light_blink"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the UPB light based on a config entry."""

    upb = hass.data[DOMAIN]["upb"]
    async_add_entities(UpbLight(upb.devices[dev], upb) for dev in upb.devices)

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_LIGHT_FADE_START, UPB_BRIGHTNESS_RATE_SCHEMA, "light_fade_start"
    )
    platform.async_register_entity_service(
        SERVICE_LIGHT_FADE_STOP, {}, "light_fade_stop"
    )
    platform.async_register_entity_service(
        SERVICE_LIGHT_UPDATE_STATUS, {}, "light_update_status"
    )
    platform.async_register_entity_service(
        SERVICE_LIGHT_BLINK, UPB_BLINK_RATE_SCHEMA, "light_blink"
    )


class UpbLight(UpbAttachedEntity, Light):
    """Representation of an UPB Light."""

    def __init__(self, element, upb):
        """Initialize an UpbLight."""
        super().__init__(element, upb)
        self._brightness = self._element.status

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._element.dimmable:
            return SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION | SUPPORT_FLASH
        return SUPPORT_FLASH

    @property
    def brightness(self):
        """Get the brightness."""
        return self._brightness

    @property
    def is_on(self) -> bool:
        """Get the current brightness."""
        return self._brightness != 0

    async def async_turn_on(self, **kwargs):
        """Turn on the light."""
        flash = kwargs.get(ATTR_FLASH)
        if flash:
            self.light_blink(0.5 if flash == "short" else 1.5)
        else:
            rate = kwargs.get(ATTR_TRANSITION, -1)
            brightness = kwargs.get(ATTR_BRIGHTNESS, 255) / 2.55
            self._element.turn_on(brightness, rate)

    async def async_turn_off(self, **kwargs):
        """Turn off the device."""
        rate = kwargs.get(ATTR_TRANSITION, -1)
        self._element.turn_off(rate)

    async def light_fade_start(self, rate, brightness=None, brightness_pct=None):
        """Start dimming of device."""
        if brightness:
            brightness_pct = brightness / 2.55
        self._element.fade_start(brightness_pct, rate)

    async def light_fade_stop(self):
        """Stop dimming of device."""
        self._element.fade_stop()

    async def light_blink(self, blink_rate):
        """Request device to blink."""
        blink_rate = int(blink_rate * 60)  # Convert seconds to 60 hz pulses
        self._element.blink(blink_rate)

    async def light_update_status(self):
        """Request the device to update its status."""
        self._element.update_status()

    def _element_changed(self, element, changeset):
        status = self._element.status
        self._brightness = round(status * 2.55) if status else 0
