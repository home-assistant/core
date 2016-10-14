"""
Group platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.group/
"""
import collections
import logging
import voluptuous as vol

from homeassistant.const import ATTR_SERVICE
from homeassistant.components.notify import (DOMAIN, ATTR_MESSAGE, ATTR_DATA,
                                             PLATFORM_SCHEMA,
                                             BaseNotificationService)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_SERVICES = "services"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SERVICES): vol.All(cv.ensure_list, [{
        vol.Required(ATTR_SERVICE): cv.slug,
        vol.Optional(ATTR_DATA): dict,
    }])
})


def update(input_dict, update_source):
    """Deep update a dictionary."""
    for key, val in update_source.items():
        if isinstance(val, collections.Mapping):
            recurse = update(input_dict.get(key, {}), val)
            input_dict[key] = recurse
        else:
            input_dict[key] = update_source[key]
    return input_dict


def get_service(hass, config):
    """Get the Group notification service."""
    return GroupNotifyPlatform(hass, config.get(CONF_SERVICES))


# pylint: disable=too-few-public-methods
class GroupNotifyPlatform(BaseNotificationService):
    """Implement the notification service for the group notify playform."""

    def __init__(self, hass, entities):
        """Initialize the service."""
        self.hass = hass
        self.entities = entities

    def send_message(self, message="", **kwargs):
        """Send message to all entities in the group."""
        payload = {ATTR_MESSAGE: message}
        payload.update({key: val for key, val in kwargs.items() if val})

        for entity in self.entities:
            sending_payload = payload.copy()
            if entity.get(ATTR_DATA) is not None:
                update(sending_payload, entity.get(ATTR_DATA))
            self.hass.services.call(DOMAIN, entity.get(ATTR_SERVICE),
                                    sending_payload)
