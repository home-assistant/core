"""
Support for MAX! devices via a CUL stick.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/maxcul/
"""
import logging

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pymaxcul==0.1.9']

DOMAIN = 'maxcul'

CONF_DEVICE_PATH = 'device_path'
CONF_DEVICE_BAUD_RATE = 'device_baud_rate'
CONF_DEVICE_ID = 'device_id'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_DEVICE_PATH): cv.string,
        vol.Required(CONF_DEVICE_BAUD_RATE): cv.positive_int,
        vol.Optional(CONF_DEVICE_ID): cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)

DATA_MAXCUL_CONNECTION = 'maxcul'

SIGNAL_THERMOSTAT_UPDATE = DOMAIN + '.thermostat_update'
SIGNAL_PUSH_BUTTON_UPDATE = DOMAIN + '.push_button_update'
SIGNAL_SHUTTER_UPDATE = DOMAIN + '.shutter_update'

ATTR_DURATION = 'duration'

SERIVCE_ENABLE_PAIRING = 'enable_pairing'

SCHEMA_SERVICE_ENABLE_PAIRING = vol.Schema({
    vol.Optional('duration', default=30): cv.positive_int,
})


def setup(hass, config):
    """
    Initialize the maxcul component.

    Reads previously paired devices from a configuration file.
    Starts the thread that communications with the CUL stick.
    Sets up appropriate callback for events from the stick.
    Sets up devices that have previously been paired.
    """
    import maxcul
    conf = config[DOMAIN]
    path = conf[CONF_DEVICE_PATH]
    baud = conf[CONF_DEVICE_BAUD_RATE]
    device_id = conf.get(CONF_DEVICE_ID)

    def callback(event, payload):
        """Handle new MAX! events."""
        if event == maxcul.EVENT_THERMOSTAT_UPDATE:
            dispatcher_send(hass, SIGNAL_THERMOSTAT_UPDATE, payload)

        elif event == maxcul.EVENT_PUSH_BUTTON_UPDATE:
            dispatcher_send(hass, SIGNAL_PUSH_BUTTON_UPDATE, payload)

        elif event == maxcul.EVENT_SHUTTER_UPDATE:
            dispatcher_send(hass, SIGNAL_SHUTTER_UPDATE, payload)
            hass.bus.fire(SIGNAL_SHUTTER_UPDATE, payload)

        elif event in [maxcul.EVENT_DEVICE_PAIRED,
                       maxcul.EVENT_DEVICE_REPAIRED]:
            device_id = payload.get(maxcul.ATTR_DEVICE_ID)
            _LOGGER.info("New MAX! device paired: %d", device_id)

        else:
            _LOGGER.warning("Unhandled event: %s", event)

    params = dict(
        device_path=path,
        baudrate=baud,
        callback=callback
    )
    if device_id:
        params['sender_id'] = device_id
    maxconn = maxcul.MaxConnection(**params)
    maxconn.start()

    hass.data[DATA_MAXCUL_CONNECTION] = maxconn

    def _service_enable_pairing(service):
        duration = service.data.get(ATTR_DURATION)
        maxconn.enable_pairing(duration)

    hass.services.register(
        DOMAIN,
        SERIVCE_ENABLE_PAIRING,
        _service_enable_pairing,
        schema=SCHEMA_SERVICE_ENABLE_PAIRING)

    return True
