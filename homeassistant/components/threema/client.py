"""Threema Gateway API client."""

import logging
import os

import aiohttp
import nacl.public
import nacl.utils

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

_BASE_URL = "https://msgapi.threema.ch"
_HTTP_UNAUTHORIZED = 401
_MSG_TYPE_TEXT = 0x01


class ThreemaConnectionError(Exception):
    """Error to indicate a connection issue with the Threema Gateway."""


class ThreemaAuthError(Exception):
    """Error to indicate invalid credentials for the Threema Gateway."""


class ThreemaSendError(Exception):
    """Error to indicate a message send failure."""


class ThreemaAPIClient:
    """Threema Gateway API client."""

    def __init__(
        self,
        hass: HomeAssistant,
        gateway_id: str,
        api_secret: str,
        private_key: str | None = None,
    ) -> None:
        """Initialize the Threema API client."""
        self.hass = hass
        self.gateway_id = gateway_id
        self.api_secret = api_secret
        self.private_key = private_key

    async def validate_credentials(self) -> None:
        """Validate the Gateway credentials by checking credits.

        Raises ThreemaAuthError for invalid credentials.
        Raises ThreemaConnectionError for other failures.
        """
        session = async_get_clientsession(self.hass)
        try:
            resp = await session.get(
                f"{_BASE_URL}/credits",
                params={"from": self.gateway_id, "secret": self.api_secret},
            )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ThreemaConnectionError(
                f"Connection error validating credentials: {err}"
            ) from err

        if resp.status == _HTTP_UNAUTHORIZED:
            raise ThreemaAuthError("Invalid Threema Gateway credentials")
        if not resp.ok:
            raise ThreemaConnectionError(
                f"Gateway error validating credentials: HTTP {resp.status}"
            )

        try:
            remaining_credits = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ThreemaConnectionError(
                f"Connection error reading validation response: {err}"
            ) from err
        _LOGGER.debug("Gateway credentials validated, credits: %s", remaining_credits)

    async def _fetch_recipient_public_key(
        self, recipient_id: str
    ) -> nacl.public.PublicKey:
        """Fetch recipient public key from Threema Gateway."""
        session = async_get_clientsession(self.hass)
        try:
            resp = await session.get(
                f"{_BASE_URL}/pubkeys/{recipient_id}",
                params={"from": self.gateway_id, "secret": self.api_secret},
            )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ThreemaSendError(
                f"Failed to fetch public key for {recipient_id}: {err}"
            ) from err

        if resp.status == _HTTP_UNAUTHORIZED:
            raise ThreemaAuthError("Invalid Threema Gateway credentials")
        if not resp.ok:
            raise ThreemaSendError(
                f"Failed to fetch public key for {recipient_id}: HTTP {resp.status}"
            )

        try:
            key_hex = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ThreemaSendError(
                f"Connection error reading public key response for {recipient_id}: {err}"
            ) from err
        try:
            return nacl.public.PublicKey(bytes.fromhex(key_hex.strip()))
        except ValueError as err:
            raise ThreemaSendError(
                f"Malformed public key received for {recipient_id}: {err}"
            ) from err

    def _build_encrypted_message(
        self, text: str, recipient_public_key: nacl.public.PublicKey
    ) -> tuple[bytes, bytes]:
        """Build and encrypt a text message for E2E delivery.

        Returns (nonce, ciphertext) as raw bytes.
        """
        assert self.private_key is not None
        text_bytes = text.encode("utf-8")
        padding_length = os.urandom(1)[0] or 255
        padding = bytes([padding_length] * padding_length)
        plaintext = bytes([_MSG_TYPE_TEXT]) + text_bytes + padding

        private_key = nacl.public.PrivateKey(bytes.fromhex(self.private_key))
        nonce = nacl.utils.random(nacl.public.Box.NONCE_SIZE)
        box = nacl.public.Box(private_key, recipient_public_key)
        encrypted = box.encrypt(plaintext, nonce)
        return encrypted.nonce, encrypted.ciphertext

    async def send_text_message(self, recipient_id: str, text: str) -> str:
        """Send a text message to a Threema ID.

        Returns the message ID on success.
        Raises ThreemaSendError on failure.
        """
        session = async_get_clientsession(self.hass)

        try:
            if self.private_key:
                _LOGGER.debug("Sending E2E encrypted message to %s", recipient_id)
                recipient_pub_key = await self._fetch_recipient_public_key(recipient_id)
                nonce, ciphertext = self._build_encrypted_message(
                    text, recipient_pub_key
                )
                resp = await session.post(
                    f"{_BASE_URL}/send_e2e",
                    data={
                        "from": self.gateway_id,
                        "to": recipient_id,
                        "secret": self.api_secret,
                        "nonce": nonce.hex(),
                        "box": ciphertext.hex(),
                    },
                )
            else:
                _LOGGER.debug("Sending simple message to %s", recipient_id)
                resp = await session.post(
                    f"{_BASE_URL}/send_simple",
                    data={
                        "from": self.gateway_id,
                        "to": recipient_id,
                        "secret": self.api_secret,
                        "text": text,
                    },
                )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ThreemaSendError(
                f"Connection error sending message to {recipient_id}: {err}"
            ) from err

        if resp.status == _HTTP_UNAUTHORIZED:
            raise ThreemaAuthError("Invalid Threema Gateway credentials")
        if not resp.ok:
            raise ThreemaSendError(
                f"Gateway error sending message to {recipient_id}: HTTP {resp.status}"
            )

        try:
            message_id = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ThreemaSendError(
                f"Connection error reading send response for {recipient_id}: {err}"
            ) from err
        _LOGGER.debug("Message sent to %s (ID: %s)", recipient_id, message_id)
        return message_id


def generate_key_pair() -> tuple[str, str]:
    """Generate a new key pair for E2E encryption.

    Returns tuple of (private_key, public_key) as hex-encoded strings.
    """
    private_key = nacl.public.PrivateKey.generate()
    return private_key.encode().hex(), private_key.public_key.encode().hex()


def derive_public_key(private_key_hex: str) -> str:
    """Derive the hex-encoded public key matching a hex-encoded private key."""
    private_key = nacl.public.PrivateKey(bytes.fromhex(private_key_hex))
    return private_key.public_key.encode().hex()
