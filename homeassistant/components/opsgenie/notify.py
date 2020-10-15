"""Opsgenie platform for notify component."""
import logging

import opsgenie_sdk
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_API_KEY, CONF_URL
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_ALIAS = "alias"
ATTR_ACTIONS = "actions"
ATTR_TAGS = "tags"
ATTR_PRIORITY = "priority"
ATTR_ENTITY = "entity"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_API_KEY): cv.string, vol.Required(CONF_URL): cv.string}
)


def get_service(hass, config, discovery_info=None):
    """Get the Opsgenie notification service."""

    apiconf = opsgenie_sdk.configuration.Configuration()
    apiconf.api_key["Authorization"] = config.get(CONF_API_KEY)
    apiconf.host = config.get(CONF_URL, "https://api.opsgenie.com")

    api_client = opsgenie_sdk.api_client.ApiClient(configuration=apiconf)

    return OpsgenieNotificationService(hass, api_client)


class OpsgenieNotificationService(BaseNotificationService):
    """Implement the notification service for Opsgenie."""

    def __init__(self, hass, api_client):
        """Initialize the service."""
        self._alert_api = opsgenie_sdk.AlertApi(api_client=api_client)
        self.hass = hass

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        data = dict(kwargs.get(ATTR_DATA) or {})

        responders = []

        if ATTR_TARGET in kwargs:
            for target in kwargs.get(ATTR_TARGET).split(","):
                if target.startswith("team:"):
                    responders.append({"type": "team", "name": target[5:]})
                elif target.startswith("escalation:"):
                    responders.append({"type": "escalation", "name": target[11:]})
                elif target.startswith("schedule:"):
                    responders.append({"type": "schedule", "name": target[9:]})
                else:
                    responders.append({"type": "user", "username": target})

        body = opsgenie_sdk.CreateAlertPayload(
            message=kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
            alias=data.get(ATTR_ALIAS, None),
            description=message,
            responders=responders,
            actions=data.get(ATTR_ACTIONS, []),
            tags=data.get(ATTR_TAGS, []),
            entity=data.get(ATTR_ENTITY, None),
            priority=data.get(ATTR_PRIORITY, None),
        )

        try:
            self._alert_api.create_alert(create_alert_payload=body)
        except opsgenie_sdk.ApiException as err:
            _LOGGER.error(err)
