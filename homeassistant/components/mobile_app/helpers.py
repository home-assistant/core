"""Helpers for mobile_app."""
import logging
import json
from typing import Callable, Dict, Tuple

from aiohttp.web import Response

from homeassistant.core import Context
from homeassistant.helpers.typing import HomeAssistantType

from .const import (ATTR_APP_DATA, ATTR_APP_ID, ATTR_APP_NAME,
                    ATTR_APP_VERSION, DATA_DELETED_IDS, ATTR_DEVICE_NAME,
                    ATTR_MANUFACTURER, ATTR_MODEL, ATTR_OS_VERSION,
                    DATA_REGISTRATIONS, ATTR_SUPPORTS_ENCRYPTION,
                    CONF_USER_ID, DOMAIN)

_LOGGER = logging.getLogger(__name__)


def get_cipher() -> Tuple[int, Callable]:
    """Return decryption function and length of key.

    Async friendly.
    """
    from nacl.secret import SecretBox
    from nacl.encoding import Base64Encoder

    def decrypt(ciphertext, key):
        """Decrypt ciphertext using key."""
        return SecretBox(key).decrypt(ciphertext, encoder=Base64Encoder)
    return (SecretBox.KEY_SIZE, decrypt)


def _decrypt_payload(key: str, ciphertext: str) -> Dict[str, str]:
    """Decrypt encrypted payload."""
    try:
        keylen, decrypt = get_cipher()
    except OSError:
        _LOGGER.warning(
            "Ignoring encrypted payload because libsodium not installed")
        return None

    if key is None:
        _LOGGER.warning(
            "Ignoring encrypted payload because no decryption key known")
        return None

    key = key.encode("utf-8")
    key = key[:keylen]
    key = key.ljust(keylen, b'\0')

    try:
        message = decrypt(ciphertext, key)
        message = json.loads(message.decode("utf-8"))
        _LOGGER.debug("Successfully decrypted mobile_app payload")
        return message
    except ValueError:
        _LOGGER.warning("Ignoring encrypted payload because unable to decrypt")
        return None


def registration_context(registration: Dict) -> Context:
    """Generate a context from a request."""
    return Context(user_id=registration[CONF_USER_ID])


def empty_okay_response(headers: Dict = None, status: int = 200) -> Response:
    """Return a Response with empty JSON object and a 200."""
    return Response(body='{}', status=status, content_type='application/json',
                    headers=headers)


def supports_encryption() -> bool:
    """Test if we support encryption."""
    try:
        import nacl   # noqa pylint: disable=unused-import
        return True
    except OSError:
        return False


def safe_registration(registration: Dict) -> Dict:
    """Return a registration without sensitive values."""
    # Sensitive values: webhook_id, secret, cloudhook_url
    return {
        ATTR_APP_DATA: registration[ATTR_APP_DATA],
        ATTR_APP_ID: registration[ATTR_APP_ID],
        ATTR_APP_NAME: registration[ATTR_APP_NAME],
        ATTR_APP_VERSION: registration[ATTR_APP_VERSION],
        ATTR_DEVICE_NAME: registration[ATTR_DEVICE_NAME],
        ATTR_MANUFACTURER: registration[ATTR_MANUFACTURER],
        ATTR_MODEL: registration[ATTR_MODEL],
        ATTR_OS_VERSION: registration[ATTR_OS_VERSION],
        ATTR_SUPPORTS_ENCRYPTION: registration[ATTR_SUPPORTS_ENCRYPTION],
    }


def savable_state(hass: HomeAssistantType) -> Dict:
    """Return a clean object containing things that should be saved."""
    return {
        DATA_DELETED_IDS: hass.data[DOMAIN][DATA_DELETED_IDS],
        DATA_REGISTRATIONS: hass.data[DOMAIN][DATA_REGISTRATIONS]
    }
