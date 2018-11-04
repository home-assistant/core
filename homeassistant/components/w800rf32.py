"""
Support for w800rf32 components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/w800rf32/

```yaml
# Example configuration.yaml entry

w800rf32:
  device: PATH_TO_DEVICE

```
"""
import logging

import voluptuous as vol

from homeassistant.const import (CONF_DEVICE,
                                 EVENT_HOMEASSISTANT_START,
                                 EVENT_HOMEASSISTANT_STOP)

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (dispatcher_send)

REQUIREMENTS = ['pyW800rf32==0.1']

DOMAIN = 'w800rf32'
DATA_W800RF32 = 'data_w800rf32'

ATTR_FIRE_EVENT = 'fire_event'
CONF_FIRE_EVENT = 'fire_event'
CONF_DEBUG = 'debug'
CONF_OFF_DELAY = 'off_delay'
CONF_DEVICE_CLASS = 'device_class'
EVENT_BUTTON_PRESSED = 'button_pressed'

RECEIVED_EVT_SUBSCRIBERS = []
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE): cv.string,
        vol.Optional(CONF_DEBUG, default=False): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the w800rf32 component."""
    # Try to load the W800rf32 module.
    import W800rf32 as w800

    # Declare the Handle event
    def handle_receive(event):
        """Handle received messages from w800rf32 gateway."""
        # Log event
        if not event.device:
            return
        _LOGGER.debug("Receive W800rf32 event in handle_receive")

        # Get device_type from device_id in hass.data
        device_id = event.device.lower()

        try:
            device_type = \
                hass.data[DOMAIN]['entities'][device_id].__class__.__name__
        except KeyError:
            return

        dispatcher_send(hass, device_type, event)

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

    hass.data[DATA_W800RF32] = w800_object
    hass.data[DOMAIN] = {'entities': {}}
    return True
