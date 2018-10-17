"""
Support for w800rf32 components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/w800rf32/

# Example configuration.yaml entry

w800rf32:
  device: PATH_TO_DEVICE

"""
import logging

import voluptuous as vol

from homeassistant.const import (
     ATTR_ENTITY_ID, ATTR_NAME, ATTR_STATE, CONF_DEVICE, CONF_DEVICES,
     EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyW800rf32']

DOMAIN = 'w800rf32'

ATTR_FIRE_EVENT = 'fire_event'
CONF_FIRE_EVENT = 'fire_event'
CONF_DEBUG = 'debug'
CONF_OFF_DELAY = 'off_delay'
EVENT_BUTTON_PRESSED = 'button_pressed'

RECEIVED_EVT_SUBSCRIBERS = []
W800_DEVICES = {}
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_DEBUG, default=False): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the w800rf32 component."""
    # Declare the Handle event
    def handle_receive(event):
        """Handle received messages from w800rf32 gateway."""
        # Log event
        if not event.device:
            return
        _LOGGER.debug("Receive W800rf32 event in handle_receive")

        # Callback to HA registered components.
        for subscriber in RECEIVED_EVT_SUBSCRIBERS:
            subscriber(event)

    # Try to load the W800rf32 module.
    import W800rf32 as w800

    # device --> /dev/ttyUSB0
    device = config[DOMAIN][CONF_DEVICE]
    w800_object = w800.Connect(device, None)

    def _start_w800rf32(event):
        w800_object.event_callback = handle_receive
    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start_w800rf32)

    def _shutdown_w800rf32(event):
        """Close connection with w800rf32."""
        w800_object.close_connection()
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown_w800rf32)

    hass.data['w800object'] = w800_object
    return True


def apply_received_command(event):
    """Apply command from w800rf32."""
    device_id = event.device.lower()
    command = event.command
    # Check if entity exists or previously added automatically
    if device_id not in W800_DEVICES:
        return

    _LOGGER.debug(
        "Device_id: %s, Command: %s",
        device_id,
        command
    )

    if command == 'On'\
            or command == 'Off':

        # Update the w800rf32 device state
        is_on = command == 'On'
        W800_DEVICES[device_id].update_state(is_on)

    # Fire event
    if W800_DEVICES[device_id].should_fire_event:
        W800_DEVICES[device_id].hass.bus.fire(
            EVENT_BUTTON_PRESSED, {
                ATTR_ENTITY_ID:
                    W800_DEVICES[device_id].entity_id,
                ATTR_STATE: command.lower()
            }
        )
        _LOGGER.debug(
            "w800rf32 fired event: (event_type: %s, %s: %s, %s: %s)",
            EVENT_BUTTON_PRESSED,
            ATTR_ENTITY_ID,
            W800_DEVICES[device_id].entity_id,
            ATTR_STATE,
            command.lower()
        )
