"""
Support for RFXtrx switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.rfxtrx/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.components.rfxtrx as rfxtrx
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['rfxtrx']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICE, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEBUG, default=DEFAULT_PAYLOAD_ON): cv.boolean,
    vol.Optional(ATTR_NAME, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(ATTR_FIREEVENT, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(ATTR_FIREEVENT, default=DEFAULT_OPTIMISTIC): cv.boolean,
    vol.Optional(ATTR_FIREEVENT, default=DEFAULT_OPTIMISTIC): cv.boolean,
})

def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the RFXtrx platform."""
    import RFXtrx as rfxtrxmod

    # Add switch from config file
    switches = rfxtrx.get_devices_from_config(config, RfxtrxSwitch)
    add_devices_callback(switches)

    def switch_update(event):
        """Callback for sensor updates from the RFXtrx gateway."""
        if not isinstance(event.device, rfxtrxmod.LightingDevice) or \
                event.device.known_to_be_dimmable:
            return

        new_device = rfxtrx.get_new_device(event, config, RfxtrxSwitch)
        if new_device:
            add_devices_callback([new_device])

        rfxtrx.apply_received_command(event)

    # Subscribe to main rfxtrx events
    if switch_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(switch_update)


class RfxtrxSwitch(rfxtrx.RfxtrxDevice, SwitchDevice):
    """Representation of a RFXtrx switch."""

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._send_command("turn_on")
