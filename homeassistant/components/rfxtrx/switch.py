"""Support for RFXtrx switches."""
import logging

import voluptuous as vol

from homeassistant.components import rfxtrx
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv

from . import (
    CONF_AUTOMATIC_ADD, CONF_DEVICES, CONF_FIRE_EVENT, CONF_SIGNAL_REPETITIONS,
    DEFAULT_SIGNAL_REPETITIONS)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {
        cv.string: vol.Schema({
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean,
        })
    },
    vol.Optional(CONF_AUTOMATIC_ADD, default=False):  cv.boolean,
    vol.Optional(CONF_SIGNAL_REPETITIONS, default=DEFAULT_SIGNAL_REPETITIONS):
        vol.Coerce(int),
})


def setup_platform(hass, config, add_entities_callback, discovery_info=None):
    """Set up the RFXtrx platform."""
    import RFXtrx as rfxtrxmod

    # Add switch from config file
    switches = rfxtrx.get_devices_from_config(config, RfxtrxSwitch)
    add_entities_callback(switches)

    def switch_update(event):
        """Handle sensor updates from the RFXtrx gateway."""
        if not isinstance(event.device, rfxtrxmod.LightingDevice) or \
                event.device.known_to_be_dimmable or \
                event.device.known_to_be_rollershutter:
            return

        new_device = rfxtrx.get_new_device(event, config, RfxtrxSwitch)
        if new_device:
            add_entities_callback([new_device])

        rfxtrx.apply_received_command(event)

    # Subscribe to main RFXtrx events
    if switch_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(switch_update)


class RfxtrxSwitch(rfxtrx.RfxtrxDevice, SwitchDevice):
    """Representation of a RFXtrx switch."""

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._send_command("turn_on")
