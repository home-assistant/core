"""Twitter platform for notify component."""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import partial
from http import HTTPStatus
import json
import logging
import mimetypes
import os

from TwitterAPI import TwitterAPI
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_CONSUMER_KEY = "consumer_key"
CONF_CONSUMER_SECRET = "consumer_secret"
CONF_ACCESS_TOKEN_SECRET = "access_token_secret"

ATTR_MEDIA = "media"

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
        vol.Required(CONF_ACCESS_TOKEN_SECRET): cv.string,
        vol.Required(CONF_CONSUMER_KEY): cv.string,
        vol.Required(CONF_CONSUMER_SECRET): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> TwitterNotificationService:
    """Get the Twitter notification service."""
    return TwitterNotificationService(
        hass,
        config[CONF_CONSUMER_KEY],
        config[CONF_CONSUMER_SECRET],
        config[CONF_ACCESS_TOKEN],
        config[CONF_ACCESS_TOKEN_SECRET],
        config.get(CONF_USERNAME),
    )


class TwitterNotificationService(BaseNotificationService):
    """Implementation of a notification service for the Twitter service."""

    def __init__(
        self,
        hass,
        consumer_key,
        consumer_secret,
        access_token_key,
        access_token_secret,
        username,
    ):
        """Initialize the service."""
        self.default_user = username
        self.hass = hass
        self.api = TwitterAPI(
            consumer_key, consumer_secret, access_token_key, access_token_secret
        )

    def send_message(self, message="", **kwargs):
        """Tweet a message, optionally with media."""
        data = kwargs.get(ATTR_DATA)
        targets = kwargs.get(ATTR_TARGET)

        media = None
        if data:
            media = data.get(ATTR_MEDIA)
            if not self.hass.config.is_allowed_path(media):
                _LOGGER.warning("'%s' is not a whitelisted directory", media)
                return

        if targets:
            for target in targets:
                callback = partial(self.send_message_callback, message, target)
                self.upload_media_then_callback(callback, media)
        else:
            callback = partial(self.send_message_callback, message, self.default_user)
            self.upload_media_then_callback(callback, media)

    def send_message_callback(self, message, user, media_id=None):
        """Tweet a message, optionally with media."""
        if user:
            user_resp = self.api.request("users/lookup", {"screen_name": user})
            user_id = user_resp.json()[0]["id"]
            if user_resp.status_code != HTTPStatus.OK:
                self.log_error_resp(user_resp)
            else:
                _LOGGER.debug("Message posted: %s", user_resp.json())

            event = {
                "event": {
                    "type": "message_create",
                    "message_create": {
                        "target": {"recipient_id": user_id},
                        "message_data": {"text": message},
                    },
                }
            }
            resp = self.api.request("direct_messages/events/new", json.dumps(event))
        else:
            resp = self.api.request(
                "statuses/update", {"status": message, "media_ids": media_id}
            )

        if resp.status_code != HTTPStatus.OK:
            self.log_error_resp(resp)
        else:
            _LOGGER.debug("Message posted: %s", resp.json())

    def upload_media_then_callback(self, callback, media_path=None) -> None:
        """Upload media."""
        if not media_path:
            callback()
            return

        with open(media_path, "rb") as file:
            total_bytes = os.path.getsize(media_path)
            (media_category, media_type) = self.media_info(media_path)
            resp = self.upload_media_init(media_type, media_category, total_bytes)

            if 199 > resp.status_code < 300:
                self.log_error_resp(resp)
                return

            media_id = resp.json()["media_id"]
            media_id = self.upload_media_chunked(file, total_bytes, media_id)

            resp = self.upload_media_finalize(media_id)
            if 199 > resp.status_code < 300:
                self.log_error_resp(resp)
                return

            if resp.json().get("processing_info") is None:
                callback(media_id)
                return

            self.check_status_until_done(media_id, callback)

    def media_info(self, media_path):
        """Determine mime type and Twitter media category for given media."""
        (media_type, _) = mimetypes.guess_type(media_path)
        media_category = self.media_category_for_type(media_type)
        _LOGGER.debug(
            "media %s is mime type %s and translates to %s",
            media_path,
            media_type,
            media_category,
        )
        return media_category, media_type

    def upload_media_init(self, media_type, media_category, total_bytes):
        """Upload media, INIT phase."""
        return self.api.request(
            "media/upload",
            {
                "command": "INIT",
                "media_type": media_type,
                "media_category": media_category,
                "total_bytes": total_bytes,
            },
        )

    def upload_media_chunked(self, file, total_bytes, media_id):
        """Upload media, chunked append."""
        segment_id = 0
        bytes_sent = 0
        while bytes_sent < total_bytes:
            chunk = file.read(4 * 1024 * 1024)
            resp = self.upload_media_append(chunk, media_id, segment_id)
            if not HTTPStatus.OK <= resp.status_code < HTTPStatus.MULTIPLE_CHOICES:
                self.log_error_resp_append(resp)
                return None
            segment_id = segment_id + 1
            bytes_sent = file.tell()
            self.log_bytes_sent(bytes_sent, total_bytes)
        return media_id

    def upload_media_append(self, chunk, media_id, segment_id):
        """Upload media, APPEND phase."""
        return self.api.request(
            "media/upload",
            {"command": "APPEND", "media_id": media_id, "segment_index": segment_id},
            {"media": chunk},
        )

    def upload_media_finalize(self, media_id):
        """Upload media, FINALIZE phase."""
        return self.api.request(
            "media/upload", {"command": "FINALIZE", "media_id": media_id}
        )

    def check_status_until_done(self, media_id, callback, *args) -> None:
        """Upload media, STATUS phase."""
        resp = self.api.request(
            "media/upload",
            {"command": "STATUS", "media_id": media_id},
            method_override="GET",
        )
        if resp.status_code != HTTPStatus.OK:
            _LOGGER.error("Media processing error: %s", resp.json())
        processing_info = resp.json()["processing_info"]

        _LOGGER.debug("media processing %s status: %s", media_id, processing_info)

        if processing_info["state"] in {"succeeded", "failed"}:
            callback(media_id)
            return

        check_after_secs = processing_info["check_after_secs"]
        _LOGGER.debug(
            "media processing waiting %s seconds to check status", str(check_after_secs)
        )

        when = datetime.now() + timedelta(seconds=check_after_secs)
        myself = partial(self.check_status_until_done, media_id, callback)
        async_track_point_in_time(self.hass, myself, when)

    @staticmethod
    def media_category_for_type(media_type):
        """Determine Twitter media category by mime type."""
        if media_type is None:
            return None

        if media_type.startswith("image/gif"):
            return "tweet_gif"
        if media_type.startswith("video/"):
            return "tweet_video"
        if media_type.startswith("image/"):
            return "tweet_image"

        return None

    @staticmethod
    def log_bytes_sent(bytes_sent, total_bytes):
        """Log upload progress."""
        _LOGGER.debug("%s of %s bytes uploaded", str(bytes_sent), str(total_bytes))

    @staticmethod
    def log_error_resp(resp):
        """Log error response."""
        obj = json.loads(resp.text)
        if "errors" in obj:
            error_message = obj["errors"]
        elif "error" in obj:
            error_message = obj["error"]
        else:
            error_message = resp.text
        _LOGGER.error("Error %s: %s", resp.status_code, error_message)

    @staticmethod
    def log_error_resp_append(resp):
        """Log error response, during upload append phase."""
        obj = json.loads(resp.text)
        error_message = obj["errors"][0]["message"]
        error_code = obj["errors"][0]["code"]
        _LOGGER.error(
            "Error %s: %s (Code %s)", resp.status_code, error_message, error_code
        )
