"""Helpers for mobile_app."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from http import HTTPStatus
import logging
from typing import Any

from aiohttp.web import Response, json_response
from nacl.encoding import Base64Encoder, HexEncoder, RawEncoder
from nacl.secret import SecretBox

from homeassistant.const import ATTR_DEVICE_ID, CONTENT_TYPE_JSON
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.json import json_bytes
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


def setup_decrypt(
    key_encoder: type[RawEncoder | HexEncoder],
) -> Callable[[bytes, bytes], bytes]:
    """Return decryption function and length of key.

    Async friendly.
    """

    def decrypt(ciphertext: bytes, key: bytes) -> bytes:
        """Decrypt ciphertext using key."""
        return SecretBox(key, encoder=key_encoder).decrypt(
            ciphertext, encoder=Base64Encoder
        )

    return decrypt


def setup_encrypt(
    key_encoder: type[RawEncoder | HexEncoder],
) -> Callable[[bytes, bytes], bytes]:
    """Return encryption function and length of key.

    Async friendly.
    """

    def encrypt(ciphertext: bytes, key: bytes) -> bytes:
        """Encrypt ciphertext using key."""
        return SecretBox(key, encoder=key_encoder).encrypt(
            ciphertext, encoder=Base64Encoder
        )

    return encrypt


def _decrypt_payload_helper(
    key: str | bytes,
    ciphertext: bytes,
    key_bytes: bytes,
    key_encoder: type[RawEncoder | HexEncoder],
) -> JsonValueType | None:
    """Decrypt encrypted payload."""
    try:
        decrypt = setup_decrypt(key_encoder)
    except OSError:
        _LOGGER.warning("Ignoring encrypted payload because libsodium not installed")
        return None

    if key is None:
        _LOGGER.warning("Ignoring encrypted payload because no decryption key known")
        return None

    msg_bytes = decrypt(ciphertext, key_bytes)
    message = json_loads(msg_bytes)
    _LOGGER.debug("Successfully decrypted mobile_app payload")
    return message


def decrypt_payload(key: str, ciphertext: bytes) -> JsonValueType | None:
    """Decrypt encrypted payload."""
    return _decrypt_payload_helper(key, ciphertext, key.encode("utf-8"), HexEncoder)


def _convert_legacy_encryption_key(key: str) -> bytes:
    """Convert legacy encryption key."""
    keylen = SecretBox.KEY_SIZE
    key_bytes = key.encode("utf-8")
    key_bytes = key_bytes[:keylen]
    return key_bytes.ljust(keylen, b"\0")


def decrypt_payload_legacy(key: str, ciphertext: bytes) -> JsonValueType | None:
    """Decrypt encrypted payload."""
    return _decrypt_payload_helper(
        key, ciphertext, _convert_legacy_encryption_key(key), RawEncoder
    )


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
    json_data = json_bytes(data)

    if registration[ATTR_SUPPORTS_ENCRYPTION]:
        encrypt = setup_encrypt(
            HexEncoder if ATTR_NO_LEGACY_ENCRYPTION in registration else RawEncoder
        )

        if ATTR_NO_LEGACY_ENCRYPTION in registration:
            key: bytes = registration[CONF_SECRET]
        else:
            key = _convert_legacy_encryption_key(registration[CONF_SECRET])

        enc_data = encrypt(json_data, key).decode("utf-8")
        json_data = json_bytes({"encrypted": True, "encrypted_data": enc_data})

    return Response(
        body=json_data, status=status, content_type=CONTENT_TYPE_JSON, headers=headers
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
