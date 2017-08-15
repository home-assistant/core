"""
Twitter platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.twitter/
"""
import json
import logging
import mimetypes
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    ATTR_DATA, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_USERNAME

REQUIREMENTS = ['TwitterAPI==2.4.6']

_LOGGER = logging.getLogger(__name__)

CONF_CONSUMER_KEY = 'consumer_key'
CONF_CONSUMER_SECRET = 'consumer_secret'
CONF_ACCESS_TOKEN_SECRET = 'access_token_secret'

ATTR_MEDIA = 'media'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Required(CONF_ACCESS_TOKEN_SECRET): cv.string,
    vol.Required(CONF_CONSUMER_KEY): cv.string,
    vol.Required(CONF_CONSUMER_SECRET): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Twitter notification service."""
    return TwitterNotificationService(
        hass,
        config[CONF_CONSUMER_KEY], config[CONF_CONSUMER_SECRET],
        config[CONF_ACCESS_TOKEN], config[CONF_ACCESS_TOKEN_SECRET],
        config.get(CONF_USERNAME)
    )


class TwitterNotificationService(BaseNotificationService):
    """Implementation of a notification service for the Twitter service."""

    def __init__(self, hass, consumer_key, consumer_secret, access_token_key,
                 access_token_secret, username):
        """Initialize the service."""
        from TwitterAPI import TwitterAPI
        self.user = username
        self.hass = hass
        self.api = TwitterAPI(consumer_key, consumer_secret, access_token_key,
                              access_token_secret)

    def send_message(self, message="", **kwargs):
        """Tweet a message, optionally with media."""
        data = kwargs.get(ATTR_DATA)

        media = None
        if data:
            media = data.get(ATTR_MEDIA)
            if not self.hass.config.is_allowed_path(media):
                _LOGGER.warning("'%s' is not a whitelisted directory", media)
                return

        media_id = self.upload_media(media)

        if self.user:
            resp = self.api.request('direct_messages/new',
                                    {'text': message, 'user': self.user,
                                     'media_ids': media_id})
        else:
            resp = self.api.request('statuses/update',
                                    {'status': message, 'media_ids': media_id})

        if resp.status_code != 200:
            self.log_error_resp(resp)

    def upload_media(self, media_path=None):
        """Upload media."""
        if not media_path:
            return None

        (media_type, _) = mimetypes.guess_type(media_path)
        total_bytes = os.path.getsize(media_path)

        file = open(media_path, 'rb')
        resp = self.upload_media_init(media_type, total_bytes)

        if 199 > resp.status_code < 300:
            self.log_error_resp(resp)
            return None

        media_id = resp.json()['media_id']
        media_id = self.upload_media_chunked(file, total_bytes, media_id)

        resp = self.upload_media_finalize(media_id)
        if 199 > resp.status_code < 300:
            self.log_error_resp(resp)

        return media_id

    def upload_media_init(self, media_type, total_bytes):
        """Upload media, INIT phase."""
        resp = self.api.request('media/upload',
                                {'command': 'INIT', 'media_type': media_type,
                                 'total_bytes': total_bytes})
        return resp

    def upload_media_chunked(self, file, total_bytes, media_id):
        """Upload media, chunked append."""
        segment_id = 0
        bytes_sent = 0
        while bytes_sent < total_bytes:
            chunk = file.read(4 * 1024 * 1024)
            resp = self.upload_media_append(chunk, media_id, segment_id)
            if resp.status_code not in range(200, 299):
                self.log_error_resp_append(resp)
                return None
            segment_id = segment_id + 1
            bytes_sent = file.tell()
            self.log_bytes_sent(bytes_sent, total_bytes)
        return media_id

    def upload_media_append(self, chunk, media_id, segment_id):
        """Upload media, append phase."""
        return self.api.request('media/upload',
                                {'command': 'APPEND', 'media_id': media_id,
                                 'segment_index': segment_id},
                                {'media': chunk})

    def upload_media_finalize(self, media_id):
        """Upload media, finalize phase."""
        return self.api.request('media/upload',
                                {'command': 'FINALIZE', 'media_id': media_id})

    @staticmethod
    def log_bytes_sent(bytes_sent, total_bytes):
        """Log upload progress."""
        _LOGGER.debug("%s of %s bytes uploaded", str(bytes_sent),
                      str(total_bytes))

    @staticmethod
    def log_error_resp(resp):
        """Log error response."""
        obj = json.loads(resp.text)
        error_message = obj['errors']
        _LOGGER.error("Error %s: %s", resp.status_code, error_message)

    @staticmethod
    def log_error_resp_append(resp):
        """Log error response, during upload append phase."""
        obj = json.loads(resp.text)
        error_message = obj['errors'][0]['message']
        error_code = obj['errors'][0]['code']
        _LOGGER.error("Error %s: %s (Code %s)", resp.status_code,
                      error_message, error_code)
