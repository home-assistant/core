"""Helpers for mobile_app."""
import json
import logging
from typing import Callable, Dict, Tuple

from aiohttp.web import Response, json_response
from nacl.encoding import Base64Encoder
from nacl.secret import SecretBox

from homeassistant.const import CONTENT_TYPE_JSON, HTTP_BAD_REQUEST, HTTP_OK
from homeassistant.core import Context
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTR_APP_DATA,
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_APP_VERSION,
    ATTR_DEVICE_ID,
    ATTR_DEVICE_NAME,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_OS_VERSION,
    ATTR_SUPPORTS_ENCRYPTION,
    CONF_SECRET,
    CONF_USER_ID,
    DATA_DELETED_IDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def setup_decrypt() -> Tuple[int, Callable]:
    """Return decryption function and length of key.

    Async friendly.
    """

    def decrypt(ciphertext, key):
        """Decrypt ciphertext using key."""
        return SecretBox(key).decrypt(ciphertext, encoder=Base64Encoder)

    return (SecretBox.KEY_SIZE, decrypt)


def setup_encrypt() -> Tuple[int, Callable]:
    """Return encryption function and length of key.

    Async friendly.
    """

    def encrypt(ciphertext, key):
        """Encrypt ciphertext using key."""
        return SecretBox(key).encrypt(ciphertext, encoder=Base64Encoder)

    return (SecretBox.KEY_SIZE, encrypt)


def _decrypt_payload(key: str, ciphertext: str) -> Dict[str, str]:
    """Decrypt encrypted payload."""
    try:
        keylen, decrypt = setup_decrypt()
    except OSError:
        _LOGGER.warning("Ignoring encrypted payload because libsodium not installed")
        return None

    if key is None:
        _LOGGER.warning("Ignoring encrypted payload because no decryption key known")
        return None

    key = key.encode("utf-8")
    key = key[:keylen]
    key = key.ljust(keylen, b"\0")

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


def empty_okay_response(headers: Dict = None, status: int = HTTP_OK) -> Response:
    """Return a Response with empty JSON object and a 200."""
    return Response(
        text="{}", status=status, content_type=CONTENT_TYPE_JSON, headers=headers
    )


def error_response(
    code: str, message: str, status: int = HTTP_BAD_REQUEST, headers: dict = None
) -> Response:
    """Return an error Response."""
    return json_response(
        {"success": False, "error": {"code": code, "message": message}},
        status=status,
        headers=headers,
    )


def supports_encryption() -> bool:
    """Test if we support encryption."""
    try:
        import nacl  # noqa: F401 pylint: disable=unused-import, import-outside-toplevel

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
    }


def webhook_response(
    data, *, registration: Dict, status: int = HTTP_OK, headers: Dict = None
) -> Response:
    """Return a encrypted response if registration supports it."""
    data = json.dumps(data, cls=JSONEncoder)

    if registration[ATTR_SUPPORTS_ENCRYPTION]:
        keylen, encrypt = setup_encrypt()

        key = registration[CONF_SECRET].encode("utf-8")
        key = key[:keylen]
        key = key.ljust(keylen, b"\0")

        enc_data = encrypt(data.encode("utf-8"), key).decode("utf-8")
        data = json.dumps({"encrypted": True, "encrypted_data": enc_data})

    return Response(
        text=data, status=status, content_type=CONTENT_TYPE_JSON, headers=headers
    )


def device_info(registration: Dict) -> Dict:
    """Return the device info for this registration."""
    return {
        "identifiers": {(DOMAIN, registration[ATTR_DEVICE_ID])},
        "manufacturer": registration[ATTR_MANUFACTURER],
        "model": registration[ATTR_MODEL],
        "device_name": registration[ATTR_DEVICE_NAME],
        "sw_version": registration[ATTR_OS_VERSION],
    }
