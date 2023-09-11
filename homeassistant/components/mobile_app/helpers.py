"""Helpers for mobile_app."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from http import HTTPStatus
import json
import logging
from typing import Any

from aiohttp.web import Response, json_response
from nacl.encoding import Base64Encoder, HexEncoder, RawEncoder
from nacl.secret import SecretBox

from homeassistant.const import ATTR_DEVICE_ID, CONTENT_TYPE_JSON
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.json import JSONEncoder
from homeassistant.util.json import JsonValueType, json_loads

from .const import (
    ATTR_APP_DATA,
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_APP_VERSION,
    ATTR_DEVICE_NAME,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NO_LEGACY_ENCRYPTION,
    ATTR_OS_VERSION,
    ATTR_SUPPORTS_ENCRYPTION,
    CONF_SECRET,
    CONF_USER_ID,
    DATA_DELETED_IDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def setup_decrypt(key_encoder) -> tuple[int, Callable]:
    """Return decryption function and length of key.

    Async friendly.
    """

    def decrypt(ciphertext, key):
        """Decrypt ciphertext using key."""
        return SecretBox(key, encoder=key_encoder).decrypt(
            ciphertext, encoder=Base64Encoder
        )

    return (SecretBox.KEY_SIZE, decrypt)


def setup_encrypt(key_encoder) -> tuple[int, Callable]:
    """Return encryption function and length of key.

    Async friendly.
    """

    def encrypt(ciphertext, key):
        """Encrypt ciphertext using key."""
        return SecretBox(key, encoder=key_encoder).encrypt(
            ciphertext, encoder=Base64Encoder
        )

    return (SecretBox.KEY_SIZE, encrypt)


def _decrypt_payload_helper(
    key: str | None,
    ciphertext: str,
    get_key_bytes: Callable[[str, int], str | bytes],
    key_encoder,
) -> JsonValueType | None:
    """Decrypt encrypted payload."""
    try:
        keylen, decrypt = setup_decrypt(key_encoder)
    except OSError:
        _LOGGER.warning("Ignoring encrypted payload because libsodium not installed")
        return None

    if key is None:
        _LOGGER.warning("Ignoring encrypted payload because no decryption key known")
        return None

    key_bytes = get_key_bytes(key, keylen)

    msg_bytes = decrypt(ciphertext, key_bytes)
    message = json_loads(msg_bytes)
    _LOGGER.debug("Successfully decrypted mobile_app payload")
    return message


def decrypt_payload(key: str | None, ciphertext: str) -> JsonValueType | None:
    """Decrypt encrypted payload."""

    def get_key_bytes(key: str, keylen: int) -> str:
        return key

    return _decrypt_payload_helper(key, ciphertext, get_key_bytes, HexEncoder)


def decrypt_payload_legacy(key: str | None, ciphertext: str) -> JsonValueType | None:
    """Decrypt encrypted payload."""

    def get_key_bytes(key: str, keylen: int) -> bytes:
        key_bytes = key.encode("utf-8")
        key_bytes = key_bytes[:keylen]
        key_bytes = key_bytes.ljust(keylen, b"\0")
        return key_bytes

    return _decrypt_payload_helper(key, ciphertext, get_key_bytes, RawEncoder)


def registration_context(registration: Mapping[str, Any]) -> Context:
    """Generate a context from a request."""
    return Context(user_id=registration[CONF_USER_ID])


def empty_okay_response(
    headers: dict | None = None, status: HTTPStatus = HTTPStatus.OK
) -> Response:
    """Return a Response with empty JSON object and a 200."""
    return Response(
        text="{}", status=status, content_type=CONTENT_TYPE_JSON, headers=headers
    )


def error_response(
    code: str,
    message: str,
    status: HTTPStatus = HTTPStatus.BAD_REQUEST,
    headers: dict | None = None,
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
        import nacl  # noqa: F401 pylint: disable=import-outside-toplevel

        return True
    except OSError:
        return False


def safe_registration(registration: dict) -> dict:
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


def savable_state(hass: HomeAssistant) -> dict:
    """Return a clean object containing things that should be saved."""
    return {
        DATA_DELETED_IDS: hass.data[DOMAIN][DATA_DELETED_IDS],
    }


def webhook_response(
    data: Any,
    *,
    registration: Mapping[str, Any],
    status: HTTPStatus = HTTPStatus.OK,
    headers: Mapping[str, str] | None = None,
) -> Response:
    """Return a encrypted response if registration supports it."""
    data = json.dumps(data, cls=JSONEncoder)

    if registration[ATTR_SUPPORTS_ENCRYPTION]:
        keylen, encrypt = setup_encrypt(
            HexEncoder if ATTR_NO_LEGACY_ENCRYPTION in registration else RawEncoder
        )

        if ATTR_NO_LEGACY_ENCRYPTION in registration:
            key = registration[CONF_SECRET]
        else:
            key = registration[CONF_SECRET].encode("utf-8")
            key = key[:keylen]
            key = key.ljust(keylen, b"\0")

        enc_data = encrypt(data.encode("utf-8"), key).decode("utf-8")
        data = json.dumps({"encrypted": True, "encrypted_data": enc_data})

    return Response(
        text=data, status=status, content_type=CONTENT_TYPE_JSON, headers=headers
    )


def device_info(registration: dict) -> DeviceInfo:
    """Return the device info for this registration."""
    return DeviceInfo(
        identifiers={(DOMAIN, registration[ATTR_DEVICE_ID])},
        manufacturer=registration[ATTR_MANUFACTURER],
        model=registration[ATTR_MODEL],
        name=registration[ATTR_DEVICE_NAME],
        sw_version=registration[ATTR_OS_VERSION],
    )
