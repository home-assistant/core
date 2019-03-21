"""Support for RFXtrx lights."""
import logging

import voluptuous as vol

from homeassistant.components import rfxtrx
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS, Light)
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv

from . import (
    CONF_AUTOMATIC_ADD, CONF_DEVICES, CONF_FIRE_EVENT, CONF_SIGNAL_REPETITIONS,
    DEFAULT_SIGNAL_REPETITIONS)

DEPENDENCIES = ['rfxtrx']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {
        cv.string: vol.Schema({
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean
        })
    },
    vol.Optional(CONF_AUTOMATIC_ADD, default=False):  cv.boolean,
    vol.Optional(CONF_SIGNAL_REPETITIONS, default=DEFAULT_SIGNAL_REPETITIONS):
        vol.Coerce(int),
})

SUPPORT_RFXTRX = SUPPORT_BRIGHTNESS


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the RFXtrx platform."""
    import RFXtrx as rfxtrxmod

    lights = rfxtrx.get_devices_from_config(config, RfxtrxLight)
    add_entities(lights)

    def light_update(event):
        """Handle light updates from the RFXtrx gateway."""
        if not isinstance(event.device, rfxtrxmod.LightingDevice) or \
                not event.device.known_to_be_dimmable:
            return

        new_device = rfxtrx.get_new_device(event, config, RfxtrxLight)
        if new_device:
            add_entities([new_device])

        rfxtrx.apply_received_command(event)

    # Subscribe to main RFXtrx events
    if light_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(light_update)


class RfxtrxLight(rfxtrx.RfxtrxDevice, Light):
    """Representation of a RFXtrx light."""

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_RFXTRX

    def turn_on(self, **kwargs):
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is None:
            self._brightness = 255
            self._send_command('turn_on')
        else:
            self._brightness = brightness
            _brightness = (brightness * 100 // 255)
            self._send_command('dim', _brightness)
