"""
Support for the signal generator from Homematic (HM-OU-CFM-TW).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.homematic_signalgen/
"""
import logging

import voluptuous as vol

from homeassistant.components.homematic import (
    ATTR_ADDRESS, ATTR_CHANNEL, ATTR_PARAM, ATTR_VALUE, DOMAIN,
    SERVICE_SET_DEVICE_VALUE)
from homeassistant.components.notify import (
    ATTR_DATA, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONF_ADDRESS
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.template as template

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ["homematic"]

CONF_VALUE = 'value'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_VALUE): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Homematic Signal Generator notification service."""
    address = config[CONF_ADDRESS]
    value = None
    if CONF_VALUE in config:
        value = config[CONF_VALUE]

    return HomematicSignalGeneratorNotificationService(hass, address, value)


class HomematicSignalGeneratorNotificationService(BaseNotificationService):
    """Implement the notification service for the Command Line service."""

    def __init__(self, hass, address, value):
        """Initialize the service."""
        self.hass = hass
        self.address = address
        self.value = value

    def send_message(self, message="", **kwargs):
        """Send a notification to the signal generator."""
        valueForSigGen = self.value

        dataFromMsg = kwargs.get(ATTR_DATA)
        if dataFromMsg is not None:
            if 'value' in dataFromMsg:
                valueForSigGen = dataFromMsg['value']

        templ = template.Template(valueForSigGen, self.hass)
        valueForSigGen = template.render_complex(templ, None)

        if valueForSigGen is None:
            _LOGGER.error("Value is null: Not invoking homematic signal generator.")

        data = {
            ATTR_ADDRESS: self.address,
            ATTR_CHANNEL: 2,
            ATTR_PARAM: "SUBMIT",
            ATTR_VALUE: valueForSigGen
        }
        _LOGGER.debug('Calling service: domain=' + DOMAIN + ';service=' + SERVICE_SET_DEVICE_VALUE +
                      ';data=' + str(data))
        self.hass.services.call(DOMAIN, SERVICE_SET_DEVICE_VALUE, data)
