"""
Support for RFXtrx cover components.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/cover.rfxtrx/
"""
import voluptuous as vol

import homeassistant.components.rfxtrx as rfxtrx
from homeassistant.components.cover import CoverDevice, PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.components.rfxtrx import (
    CONF_AUTOMATIC_ADD, CONF_FIRE_EVENT, DEFAULT_SIGNAL_REPETITIONS,
    CONF_SIGNAL_REPETITIONS, CONF_DEVICES)
from homeassistant.helpers import config_validation as cv

DEPENDENCIES = ['rfxtrx']

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


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the RFXtrx cover."""
    import RFXtrx as rfxtrxmod

    covers = rfxtrx.get_devices_from_config(config, RfxtrxCover)
    add_devices(covers)

    def cover_update(event):
        """Handle cover updates from the RFXtrx gateway."""
        if not isinstance(event.device, rfxtrxmod.LightingDevice) or \
                event.device.known_to_be_dimmable or \
                not event.device.known_to_be_rollershutter:
            return

        new_device = rfxtrx.get_new_device(event, config, RfxtrxCover)
        if new_device:
            add_devices([new_device])

        rfxtrx.apply_received_command(event)

    # Subscribe to main RFXtrx events
    if cover_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(cover_update)


class RfxtrxCover(rfxtrx.RfxtrxDevice, CoverDevice):
    """Representation of a RFXtrx cover."""

    @property
    def should_poll(self):
        """Return the polling state. No polling available in RFXtrx cover."""
        return False

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return None

    def open_cover(self, **kwargs):
        """Move the cover up."""
        self._send_command("roll_up")

    def close_cover(self, **kwargs):
        """Move the cover down."""
        self._send_command("roll_down")

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._send_command("stop_roll")
