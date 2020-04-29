"""Support for Tellstick lights using Tellstick Net."""
import logging

from homeassistant.components import light, tellduslive
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .entry import TelldusLiveEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up tellduslive sensors dynamically."""

    async def async_discover_light(device_id):
        """Discover and add a discovered sensor."""
        client = hass.data[tellduslive.DOMAIN]
        async_add_entities([TelldusLiveLight(client, device_id)])

    async_dispatcher_connect(
        hass,
        tellduslive.TELLDUS_DISCOVERY_NEW.format(light.DOMAIN, tellduslive.DOMAIN),
        async_discover_light,
    )


class TelldusLiveLight(TelldusLiveEntity, LightEntity):
    """Representation of a Tellstick Net light."""

    def __init__(self, client, device_id):
        """Initialize the  Tellstick Net light."""
        super().__init__(client, device_id)
        self._last_brightness = self.brightness

    def changed(self):
        """Define a property of the device that might have changed."""
        self._last_brightness = self.brightness
        self._update_callback()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self.device.dim_level

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.device.is_on

    def turn_on(self, **kwargs):
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._last_brightness)
        if brightness == 0:
            fallback_brightness = 100
            _LOGGER.info(
                "Setting brightness to %d%%, because it was 0", fallback_brightness
            )
            brightness = int(fallback_brightness * 255 / 100)
        self.device.dim(level=brightness)
        self.changed()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self.device.turn_off()
        self.changed()
