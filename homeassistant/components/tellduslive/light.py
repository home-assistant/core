"""Support for Tellstick lights using Tellstick Net."""

import logging
from typing import Any

from homeassistant.components import light
from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, TELLDUS_DISCOVERY_NEW
from .entity import TelldusLiveEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up tellduslive sensors dynamically."""

    async def async_discover_light(device_id):
        """Discover and add a discovered sensor."""
        client = hass.data[DOMAIN]
        async_add_entities([TelldusLiveLight(client, device_id)])

    async_dispatcher_connect(
        hass,
        TELLDUS_DISCOVERY_NEW.format(light.DOMAIN, DOMAIN),
        async_discover_light,
    )


class TelldusLiveLight(TelldusLiveEntity, LightEntity):
    """Representation of a Tellstick Net light."""

    _attr_name = None
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, client, device_id):
        """Initialize the  Tellstick Net light."""
        super().__init__(client, device_id)
        self._last_brightness = self.brightness

    def changed(self):
        """Define a property of the device that might have changed."""
        self._last_brightness = self.brightness
        self.schedule_update_ha_state()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self.device.dim_level

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.device.is_on

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._last_brightness)
        if brightness == 0:
            fallback_brightness = 100
            _LOGGER.debug(
                "Setting brightness to %d%%, because it was 0", fallback_brightness
            )
            brightness = int(fallback_brightness * 255 / 100)
        self.device.dim(level=brightness)
        self.changed()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self.device.turn_off()
        self.changed()
