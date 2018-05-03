"""
Facebook platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.facebook/
"""
import json
import logging

from aiohttp.hdrs import CONTENT_TYPE
import asyncio
import requests
import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.notify import (
    ATTR_DATA, ATTR_TARGET, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import (CONTENT_TYPE_JSON, HTTP_BAD_REQUEST)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_ALLOWED_CHAT_IDS = 'allowed_chat_ids'
CONF_PAGE_ACCESS_TOKEN = 'page_access_token'
BASE_URL = 'https://graph.facebook.com/v2.6/me/messages'
CREATE_BROADCAST_URL = 'https://graph.facebook.com/v2.11/me/message_creatives'
SEND_BROADCAST_URL = 'https://graph.facebook.com/v2.11/me/broadcast_messages'
FACEBOOK_HANDLER_URL = '/api/facebook_webhooks'
EVENT_FACEBOOK_MESSAGE = 'facebook_message'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PAGE_ACCESS_TOKEN): cv.string,
    vol.Optional(CONF_ALLOWED_CHAT_IDS):
        vol.All(cv.ensure_list, [vol.Coerce(int)]),
})


def get_service(hass, config, discovery_info=None):
    """Get the Facebook notification service."""
    hass.http.register_view(FacebookReceiver(hass, config))
    return FacebookNotificationService(config[CONF_PAGE_ACCESS_TOKEN])


class FacebookNotificationService(BaseNotificationService):
    """Implementation of a notification service for the Facebook service."""

    def __init__(self, access_token):
        """Initialize the service."""
        self.page_access_token = access_token

    def send_message(self, message="", **kwargs):
        """Send some message."""
        payload = {'access_token': self.page_access_token}
        targets = kwargs.get(ATTR_TARGET)
        data = kwargs.get(ATTR_DATA)

        body_message = {"text": message}

        if data is not None:
            body_message.update(data)
            # Only one of text or attachment can be specified
            if 'attachment' in body_message:
                body_message.pop('text')

        if not targets:
            _LOGGER.error("At least 1 target is required")
            return

        # broadcast message
        if targets[0].lower() == 'broadcast':
            broadcast_create_body = {"messages": [body_message]}
            _LOGGER.debug("Broadcast body %s : ", broadcast_create_body)

            resp = requests.post(CREATE_BROADCAST_URL,
                                 data=json.dumps(broadcast_create_body),
                                 params=payload,
                                 headers={CONTENT_TYPE: CONTENT_TYPE_JSON},
                                 timeout=10)
            _LOGGER.debug("FB Messager broadcast id %s : ", resp.json())

            # at this point we get broadcast id
            broadcast_body = {
                "message_creative_id": resp.json().get('message_creative_id'),
                "notification_type": "REGULAR",
            }

            resp = requests.post(SEND_BROADCAST_URL,
                                 data=json.dumps(broadcast_body),
                                 params=payload,
                                 headers={CONTENT_TYPE: CONTENT_TYPE_JSON},
                                 timeout=10)
            if resp.status_code != 200:
                log_error(resp)

        # non-broadcast message
        else:
            for target in targets:
                # If the target starts with a "+", it's a phone number,
                # otherwise it's a user id.
                if target.startswith('+'):
                    recipient = {"phone_number": target}
                else:
                    recipient = {"id": target}

                body = {
                    "recipient": recipient,
                    "message": body_message
                }
                resp = requests.post(BASE_URL, data=json.dumps(body),
                                     params=payload,
                                     headers={CONTENT_TYPE: CONTENT_TYPE_JSON},
                                     timeout=10)
                if resp.status_code != 200:
                    log_error(resp)


def log_error(response):
    """Log error message."""
    obj = response.json()
    error_message = obj['error']['message']
    error_code = obj['error']['code']

    _LOGGER.error(
        "Error %s : %s (Code %s)", response.status_code, error_message,
        error_code)


class FacebookReceiver(HomeAssistantView):
    """Handle webhooks from Facebook."""

    requires_auth = False
    url = FACEBOOK_HANDLER_URL
    name = 'api:facebook_webhooks'

    def __init__(self, hass, config):
        """Initialize the class."""
        self.hass = hass
        self.token = config[CONF_PAGE_ACCESS_TOKEN]
        self.allowed_chat_ids = config.get(CONF_ALLOWED_CHAT_IDS)

    @asyncio.coroutine
    def get(self, request):
        """Accept the GET verification from facebook."""

        data = request.query

        if data.get("hub.mode") == "subscribe" and data.get("hub.challenge"):
            if not data.get("hub.verify_token") == self.token:
                return "token mismatch", 403

        return data.get("hub.challenge"), 200

    @asyncio.coroutine
    def post(self, request):
        """Accept the POST from facebook."""

        try:
            data = yield from request.json()
        except ValueError:
            return self.json_message('Invalid JSON specified',
                                     HTTP_BAD_REQUEST)

        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:

                if messaging_event.get("message"):

                    sender_id = messaging_event["sender"]["id"]
                    message_text = messaging_event["message"]["text"]

                    if message_text == "get my id":
                        self.reply_with_id(sender_id)
                        return "ok", 200

                    if self.allowed_chat_ids is not None:
                        if int(sender_id) in self.allowed_chat_ids:
                            _LOGGER.debug("Received facebook message.")
                            event_data = {
                                'sender_id': sender_id,
                                'message': message_text,
                                'payload': None
                            }

                            if "quick_reply" in messaging_event["message"]:
                                event_data['payload'] = \
                                    messaging_event["message"]["quick_reply"][
                                        "payload"]

                            self.hass.bus.async_fire(EVENT_FACEBOOK_MESSAGE,
                                                     event_data)
                        else:
                            _LOGGER.warn(
                                ("Received message on facebook webhook from "
                                 "sender not in allowed chat ids."))
                    else:
                        _LOGGER.warn(
                            "Recieved message but no allowed senders defined")

        return "ok", 200

    def reply_with_id(self, sender_id):
        """Reply with the id of the sender to make configuration easier."""

        message_text = "Your id is {}".format(sender_id)
        params = {
            "access_token": self.token
        }
        headers = {
            "Content-Type": "application/json"
        }
        data = json.dumps({
            "recipient": {
                "id": sender_id
            },
            "message": {
                "text": message_text
            }
        })

        resp = requests.post(BASE_URL, params=params, headers=headers,
                             data=data)
        if resp.status_code != 200:
            log_error(resp)
