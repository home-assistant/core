"""
Support for RFXtrx lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.rfxtrx/
"""
import logging

import homeassistant.components.rfxtrx as rfxtrx
from homeassistant.components.light import ATTR_BRIGHTNESS, Light

DEPENDENCIES = ['rfxtrx']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = rfxtrx.DEFAULT_SCHEMA


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the RFXtrx platform."""
    import RFXtrx as rfxtrxmod

    lights = rfxtrx.get_devices_from_config(config, RfxtrxLight)
    add_devices_callback(lights)

    def light_update(event):
        """Callback for light updates from the RFXtrx gateway."""
        if not isinstance(event.device, rfxtrxmod.LightingDevice) or \
                not event.device.known_to_be_dimmable:
            return

        new_device = rfxtrx.get_new_device(event, config, RfxtrxLight)
        if new_device:
            add_devices_callback([new_device])

        rfxtrx.apply_received_command(event)

    # Subscribe to main rfxtrx events
    if light_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(light_update)


class RfxtrxLight(rfxtrx.RfxtrxDevice, Light):
    """Represenation of a RFXtrx light."""

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    def turn_on(self, **kwargs):
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is None:
            self._brightness = 255
            self._send_command("turn_on")
        else:
            self._brightness = brightness
            _brightness = (brightness * 100 // 255)
            self._send_command("dim", _brightness)
