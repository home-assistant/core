"""Helpers for mobile_app."""
import json
import logging
from typing import Callable, Dict, Tuple

from aiohttp.web import Response
from nacl.encoding import Base64Encoder
from nacl.secret import SecretBox

from homeassistant.components.mobile_app.const import (
    ATTR_SUPPORTS_ENCRYPTION,
    CONF_SECRET,
)
from homeassistant.const import HTTP_OK
from homeassistant.helpers.json import JSONEncoder

_LOGGER = logging.getLogger(__name__)


def setup_encrypt() -> Tuple[int, Callable]:
    """Return encryption function and length of key.

    Async friendly.
    """

    def encrypt(ciphertext, key):
        """Encrypt ciphertext using key."""
        return SecretBox(key).encrypt(ciphertext, encoder=Base64Encoder)

    return (SecretBox.KEY_SIZE, encrypt)


def empty_okay_response(headers: Dict = None, status: int = HTTP_OK) -> Response:
    """Return a Response with empty JSON object and a 200."""
    return Response(
        text="{}", status=status, content_type="application/json", headers=headers
    )


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
        text=data, status=status, content_type="application/json", headers=headers
    )
