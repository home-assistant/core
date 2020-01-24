"""Cisco Webex Teams notify component."""
import asyncio
import json
import logging

import async_timeout
from jinja2 import Environment
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_ROOM_ID = "room_id"
# Top level attributes in 'data'
# ATTR_FILENAME = "attachment"

ATTR_ATTACHMENT_URL = "attachment_url"

ATTR_ICON_URL = "icon_url"

ATTR_STATUS = "status"


_RESOURCE = "https://api.ciscospark.com/v1/messages"

####
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_TOKEN): cv.string, vol.Required(CONF_ROOM_ID): cv.string}
)


async def async_get_service(hass, config, discovery_info=None):
    """Get the CiscoWebexTeams notification service."""
    return CiscoWebexTeamsNotificationService(
        hass, config[CONF_TOKEN], config[CONF_ROOM_ID]
    )


JSON_TEMPLATE = """
{
    "contentType": "application/vnd.microsoft.card.adaptive",
    "content": {
        "type": "AdaptiveCard",
        "version": "1.0",
        "body": [
            {
                "type": "Container",
                "items": [
                    {
                        "type": "ColumnSet",
                        "columns": [
                            {
                                "type": "Column",
                                "width": "auto",
                                "items": [
                                    {
                                        "type": "Image",
                                        "url": "{{icon or "https://community-home-assistant-assets.s3-us-west-2.amazonaws.com/original/2X/6/6a99ebb8d0b585a00b407123ff76964cb3e18780.png"}}",
                                        "size": "Small"
                                    }
                                ]
                                {% if status is not none %}
                                ,"backgroundImage": {
                                    "url": "https://webex-teams-static-image-store.s3.us-east-2.amazonaws.com/{{status}}.png",
                                    "fillMode": "RepeatVertically"
                                }
                                {% endif %}
                            },{
                                "type": "Column",
                                "width": "stretch",

                                "items": [
                                    {% if start_date is not none %}
                                    {
                                        "type": "TextBlock",
                                        "text": "{{start_date}}",
                                        "horizontalAlignment": "Center"
                                    },
                                    {% endif %}
                                    {% if title is not none %}
                                    {
                                        "type": "TextBlock",
                                        "text": "{{title}}",
                                        "size": "Large",
                                        "horizontalAlignment": "Left"
                                    },
                                    {% endif %}
                                    {
                                        "type": "TextBlock",
                                        "horizontalAlignment": "Left",
                                        "size": "Medium",
                                        "height": "stretch",
                                        "text": "{{message}}"
                                    }
                                ],
                                "style": "default"
                            }
                        ]
                    }
                ]
            }
            {% if attachment_url is not none %}
            ,{
                "type": "Image",
                "url": "{{attachment_url}}",
                "size": "auto"
            }
            {% endif %}
        ]
    }
}
"""


class CiscoWebexTeamsNotificationService(BaseNotificationService):
    """The Cisco Webex Teams Notification Service."""

    def __init__(self, hass, token, room):
        """Initialize the service."""
        self._hass = hass
        self.room = room
        self.token = token

    async def async_send_message(self, message="", **kwargs):
        """Send a message to a user."""

        data = kwargs.get(ATTR_DATA) or {}

        icon_url = data.get(ATTR_ICON_URL)
        attachment_url = data.get(ATTR_ATTACHMENT_URL)
        status = data.get(ATTR_STATUS)

        if attachment_url is not None:
            if not attachment_url.startswith("http"):
                _LOGGER.error("URL should start with http or https")
                return

        # Icon

        if icon_url is not None:
            if not icon_url.startswith("http"):
                _LOGGER.error("URL should start with http or https")
                return

        title = ""
        if kwargs.get(ATTR_TITLE) is not None:
            title = "{}".format(kwargs.get(ATTR_TITLE))

        attachment_list = list()
        env = Environment(lstrip_blocks=True, trim_blocks=True)
        env.filters["jsonify"] = json.dumps

        jdata = env.from_string(JSON_TEMPLATE).render(
            title=title,
            message=message,
            icon=icon_url,
            attachment_url=attachment_url,
            status=status,
        )

        attachment_list.append(json.loads(jdata))

        _LOGGER.debug("Sending payload to webex teams %s", attachment_list)

        payload = {
            "roomId": f"{self.room}",
            "markdown": f"{title}{message}",
            "attachments": attachment_list,
        }
        session = async_get_clientsession(self._hass)

        _LOGGER.debug("Attempting call WebEx Teams service at %s", _RESOURCE)

        try:
            with async_timeout.timeout(10):
                response = await session.post(
                    _RESOURCE,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.token}",
                    },
                    data=json.dumps(payload),
                )

                result = await response.text()

            if response.status != 200 or "error" in result:
                _LOGGER.error(
                    "Teams API returned http status %d, response %s",
                    response.status,
                    result,
                )
            _LOGGER.info(
                "Message sent successfully, message ID: %s", json.loads(result)["id"]
            )
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout accessing Webex Teams")
