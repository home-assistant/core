"""Support for Lutron Caseta lights."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN,
    SUPPORT_BRIGHTNESS,
    Light,
)

from . import LUTRON_CASETA_SMARTBRIDGE, LutronCasetaDevice

_LOGGER = logging.getLogger(__name__)


def to_lutron_level(level):
    """Convert the given Home Assistant light level (0-255) to Lutron (0-100)."""
    return int(round((level * 100) / 255))


def to_hass_level(level):
    """Convert the given Lutron (0-100) light level to Home Assistant (0-255)."""
    return int((level * 255) // 100)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Lutron Caseta lights."""
    entities = []
    bridge = hass.data[LUTRON_CASETA_SMARTBRIDGE]
    light_devices = bridge.get_devices_by_domain(DOMAIN)
    for light_device in light_devices:
        entity = LutronCasetaLight(light_device, bridge)
        entities.append(entity)

    async_add_entities(entities, True)


class LutronCasetaLight(LutronCasetaDevice, Light):
    """Representation of a Lutron Light, including dimmable."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return to_hass_level(self._device["current_state"])

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        self._smartbridge.set_value(self.device_id, to_lutron_level(brightness))

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        self._smartbridge.set_value(self.device_id, 0)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device["current_state"] > 0

    async def async_update(self):
        """Call when forcing a refresh of the device."""
        self._device = self._smartbridge.get_device_by_id(self.device_id)
        _LOGGER.debug(self._device)
