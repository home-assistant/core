"""Sinch platform for notify component."""
from aiohttp.hdrs import CONTENT_TYPE
from homeassistant.const import CONF_API_KEY, CONF_RECIPIENT, CONTENT_TYPE_JSON
from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService

import logging
import requests
import voluptuous as vol
import json
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

DOMAIN = "sinch_sms"

BASE_URL = "https://sms.api.sinch.com/xms/v1/"
CONF_SERVICE_PLAN_ID = "service_plan_id"
CONF_FROM_NUMBER = "from_number"

PLATFORM_SCHEMA = vol.Schema(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Required(CONF_SERVICE_PLAN_ID): cv.string,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_RECIPIENT, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Required(CONF_FROM_NUMBER): cv.string,
            }
        )
    )
)


def get_service(hass, config, discovery_info=None):
    """Get the Sinch notification service."""
    return SinchNotificationService(config)


class SinchNotificationService(BaseNotificationService):
    """Implementation of a notification service for the Sinch service."""

    def __init__(self, config):
        """Initialize the service."""
        self.api_key = config.get(CONF_API_KEY)
        self.recipient = config.get(CONF_RECIPIENT)
        self.service_plan_id = config.get(CONF_SERVICE_PLAN_ID)
        self.from_number = config.get(CONF_FROM_NUMBER)

        print(self.from_number)

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""

        data = {"from": self.from_number, "to": self.recipient, "body": message}

        resp = requests.post(
            BASE_URL + self.service_plan_id + "/batches",
            data=json.dumps(data),
            headers={
                CONTENT_TYPE: CONTENT_TYPE_JSON,
                "Authorization": "Bearer {}".format(self.api_key),
            },
            timeout=10,
        )

        if (resp.status_code == 200) or (resp.status_code == 201):

            _LOGGER.info("Successfully sent sms!")
            return True

        _LOGGER.error("Error %s : %s", resp.status_code, resp.text)
