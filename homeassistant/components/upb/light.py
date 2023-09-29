"""Platform for UPB light integration."""
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_FLASH,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UpbAttachedEntity
from .const import DOMAIN, UPB_BLINK_RATE_SCHEMA, UPB_BRIGHTNESS_RATE_SCHEMA

SERVICE_LIGHT_FADE_START = "light_fade_start"
SERVICE_LIGHT_FADE_STOP = "light_fade_stop"
SERVICE_LIGHT_BLINK = "light_blink"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UPB light based on a config entry."""

    upb = hass.data[DOMAIN][config_entry.entry_id]["upb"]
    unique_id = config_entry.entry_id
    async_add_entities(
        UpbLight(upb.devices[dev], unique_id, upb) for dev in upb.devices
    )

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_LIGHT_FADE_START, UPB_BRIGHTNESS_RATE_SCHEMA, "async_light_fade_start"
    )
    platform.async_register_entity_service(
        SERVICE_LIGHT_FADE_STOP, {}, "async_light_fade_stop"
    )
    platform.async_register_entity_service(
        SERVICE_LIGHT_BLINK, UPB_BLINK_RATE_SCHEMA, "async_light_blink"
    )


class UpbLight(UpbAttachedEntity, LightEntity):
    """Representation of a UPB Light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, element, unique_id, upb):
        """Initialize an UpbLight."""
        super().__init__(element, unique_id, upb)
        self._brightness = self._element.status

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self._element.dimmable:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[str]:
        """Flag supported color modes."""
        return {self.color_mode}

    @property
    def supported_features(self) -> LightEntityFeature:
        """Flag supported features."""
        if self._element.dimmable:
            return LightEntityFeature.TRANSITION | LightEntityFeature.FLASH
        return LightEntityFeature.FLASH

    @property
    def brightness(self):
        """Get the brightness."""
        return self._brightness

    @property
    def is_on(self) -> bool:
        """Get the current brightness."""
        return self._brightness != 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        if flash := kwargs.get(ATTR_FLASH):
            await self.async_light_blink(0.5 if flash == "short" else 1.5)
        else:
            rate = kwargs.get(ATTR_TRANSITION, -1)
            brightness = round(kwargs.get(ATTR_BRIGHTNESS, 255) / 2.55)
            self._element.turn_on(brightness, rate)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        rate = kwargs.get(ATTR_TRANSITION, -1)
        self._element.turn_off(rate)

    async def async_light_fade_start(self, rate, brightness=None, brightness_pct=None):
        """Start dimming of device."""
        if brightness is not None:
            brightness_pct = round(brightness / 2.55)
        self._element.fade_start(brightness_pct, rate)

    async def async_light_fade_stop(self):
        """Stop dimming of device."""
        self._element.fade_stop()

    async def async_light_blink(self, blink_rate):
        """Request device to blink."""
        blink_rate = int(blink_rate * 60)  # Convert seconds to 60 hz pulses
        self._element.blink(blink_rate)

    async def async_update(self) -> None:
        """Request the device to update its status."""
        self._element.update_status()

    def _element_changed(self, element, changeset):
        status = self._element.status
        self._brightness = round(status * 2.55) if status else 0
