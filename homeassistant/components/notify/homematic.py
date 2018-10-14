"""
Notification support for Homematic.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.homematic/
"""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    BaseNotificationService, PLATFORM_SCHEMA, ATTR_DATA)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.homematic import (
    DOMAIN, SERVICE_SET_DEVICE_VALUE, ATTR_ADDRESS, ATTR_CHANNEL, ATTR_PARAM,
    ATTR_VALUE, ATTR_INTERFACE)
import homeassistant.helpers.template as template_helper

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ["homematic"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(ATTR_ADDRESS): vol.All(cv.string, vol.Upper),
    vol.Required(ATTR_CHANNEL): vol.Coerce(int),
    vol.Required(ATTR_PARAM): vol.All(cv.string, vol.Upper),
    vol.Required(ATTR_VALUE): cv.match_all,
    vol.Optional(ATTR_INTERFACE): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Homematic notification service."""
    data = {
        ATTR_ADDRESS: config[ATTR_ADDRESS],
        ATTR_CHANNEL: config[ATTR_CHANNEL],
        ATTR_PARAM: config[ATTR_PARAM],
        ATTR_VALUE: config[ATTR_VALUE]
    }
    if ATTR_INTERFACE in config:
        data[ATTR_INTERFACE] = config[ATTR_INTERFACE]

    return HomematicNotificationService(hass, data)


class HomematicNotificationService(BaseNotificationService):
    """Implement the notification service for Homematic."""

    def __init__(self, hass, data):
        """Initialize the service."""
        self.hass = hass
        self.data = data

    def send_message(self, message="", **kwargs):
        """Send a notification to the device."""
        attr_data = kwargs.get(ATTR_DATA)
        if attr_data is not None:
            if 'address' in attr_data:
                self.data[ATTR_ADDRESS] = attr_data['address']
            if 'channel' in attr_data:
                self.data[ATTR_CHANNEL] = attr_data['channel']
            if 'param' in attr_data:
                self.data[ATTR_PARAM] = attr_data['param']
            if 'value' in attr_data:
                self.data[ATTR_VALUE] = attr_data['value']
            if 'interface' in attr_data:
                self.data[ATTR_INTERFACE] = attr_data['interface']

        if self.data[ATTR_VALUE] is not None:
            templ = template_helper.Template(self.data[ATTR_VALUE], self.hass)
            self.data[ATTR_VALUE] = template_helper.render_complex(templ, None)

        _LOGGER.debug("Calling service: domain=%s;service=%s;data=%s",
                      DOMAIN, SERVICE_SET_DEVICE_VALUE, str(self.data))
        self.hass.services.call(DOMAIN, SERVICE_SET_DEVICE_VALUE, self.data)
