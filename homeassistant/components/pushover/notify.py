"""Pushover platform for notify component."""

import logging
import base64
import hmac
import hashlib
import os
import gzip
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from cryptography.hazmat.backends import default_backend
from typing import Any

from pushover_complete import BadAPIRequestError, PushoverAPI

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_ATTACHMENT,
    ATTR_CALLBACK_URL,
    ATTR_EXPIRE,
    ATTR_HTML,
    ATTR_PRIORITY,
    ATTR_RETRY,
    ATTR_SOUND,
    ATTR_TIMESTAMP,
    ATTR_TTL,
    ATTR_URL,
    ATTR_URL_TITLE,
    ATTR_ENCRYPTED_KEY,
    CONF_USER_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> PushoverNotificationService | None:
    """Get the Pushover notification service."""
    if discovery_info is None:
        return None
    # Uses legacy hass.data[DOMAIN] pattern
    # pylint: disable-next=home-assistant-use-runtime-data
    pushover_api: PushoverAPI = hass.data[DOMAIN][discovery_info["entry_id"]]
    return PushoverNotificationService(
        hass, pushover_api, discovery_info[CONF_USER_KEY]
    )


class PushoverNotificationService(BaseNotificationService):
    """Implement the notification service for Pushover."""

    def __init__(
        self, hass: HomeAssistant, pushover: PushoverAPI, user_key: str
    ) -> None:
        """Initialize the service."""
        self._hass = hass
        self._user_key = user_key
        self.pushover = pushover


    def encrypt(plaintext: str, key_hex: str) -> str:
        """Encrypt the plaintext using AES-256-CBC with gzip compression and HMAC-SHA256."""
        key = bytes.fromhex(key_hex)

        iv = os.urandom(16)
        compressed = gzip.compress(plaintext.encode(), compresslevel=9)
        padder = PKCS7(128).padder()
        padded = padder.update(compressed) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ct = encryptor.update(padded) + encryptor.finalize()
        h = hmac.new(key, iv + ct, hashlib.sha256).digest()
        final = iv + ct + h
        return base64.b64encode(final).decode()

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""

        # Extract params from data dict
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA) or {}
        url = data.get(ATTR_URL)
        url_title = data.get(ATTR_URL_TITLE)
        priority = data.get(ATTR_PRIORITY)
        retry = data.get(ATTR_RETRY)
        expire = data.get(ATTR_EXPIRE)
        ttl = data.get(ATTR_TTL)
        callback_url = data.get(ATTR_CALLBACK_URL)
        timestamp = data.get(ATTR_TIMESTAMP)
        sound = data.get(ATTR_SOUND)
        html = 1 if data.get(ATTR_HTML, False) else 0
        encrypted_key = data.get(ATTR_ENCRYPTED_KEY)
        encrypted = 1 if encrypted_key else 0

        # Check for attachment
        if (image := data.get(ATTR_ATTACHMENT)) is not None:
            # Only allow attachments from whitelisted paths, check valid path
            if self._hass.config.is_allowed_path(data[ATTR_ATTACHMENT]):
                # try to open it as a normal file.
                try:
                    # pylint: disable-next=consider-using-with
                    file_handle = open(data[ATTR_ATTACHMENT], "rb")
                    # Replace the attachment identifier with file object.
                    image = file_handle
                # pylint: disable-next=home-assistant-action-swallowed-exception
                except OSError as ex_val:
                    _LOGGER.error(ex_val)
                    # Remove attachment key to send without attachment.
                    image = None
            else:
                _LOGGER.error("Path is not whitelisted")
                # Remove attachment key to send without attachment.
                image = None

        # Encrypt message and title if encrypted_key is provided
        if encrypted_key:
            message = self.encrypt(message, encrypted_key)
            if title is not None:
                title = self.encrypt(title, encrypted_key)

        try:
            self.pushover.send_message(
                user=self._user_key,
                message=message,
                device=",".join(kwargs.get(ATTR_TARGET, [])),
                title=title,
                url=url,
                url_title=url_title,
                image=image,
                priority=priority,
                retry=retry,
                expire=expire,
                callback_url=callback_url,
                timestamp=timestamp,
                sound=sound,
                html=html,
                ttl=ttl,
                encrypted=encrypted,
            )
        except BadAPIRequestError as err:
            raise HomeAssistantError(str(err)) from err
