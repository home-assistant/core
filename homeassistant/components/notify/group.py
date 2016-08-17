"""
Group platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.group/
"""
import collections
import logging
import voluptuous as vol

from homeassistant.const import (CONF_PLATFORM, CONF_NAME,
                                 CONF_ENTITY_ID)
from homeassistant.components.notify import (DOMAIN, ATTR_MESSAGE, ATTR_DATA,
                                             BaseNotificationService)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_ENTITIES = "entities"

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): "group",
    vol.Required(CONF_NAME): vol.Coerce(str),
    vol.Required(CONF_ENTITIES): vol.All(cv.ensure_list, [{
        vol.Required(CONF_ENTITY_ID): vol.Any(cv.string, None),
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
    return GroupNotifyPlatform(hass, config.get(CONF_ENTITIES))


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
            self.hass.services.call(DOMAIN, entity.get(CONF_ENTITY_ID),
                                    sending_payload)
