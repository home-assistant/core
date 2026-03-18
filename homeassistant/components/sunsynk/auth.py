"""SunSynk Authentication module."""

import base64
from dataclasses import dataclass
import hashlib
import logging
import time

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
import httpx
from sunsynk_api_client import SunSynk

from .const import SunSynkAuthError

_LOGGER = logging.getLogger(__name__)


@dataclass
class AuthResult:
    """Result of authentication."""

    access_token: str
    expires_in: int
    token_type: str


def _to_pem_public_key(base64_key: str) -> str:
    """Convert Base64 encoded public key to PEM format."""
    chunks = [base64_key[i : i + 64] for i in range(0, len(base64_key), 64)]
    return (
        "-----BEGIN PUBLIC KEY-----\n"
        + "\n".join(chunks)
        + "\n-----END PUBLIC KEY-----\n"
    )


def _encrypt_password(password: str, public_key_base64: str) -> str:
    """Encrypt password using RSA with PKCS1 padding."""
    public_key_pem = _to_pem_public_key(public_key_base64)
    loaded_key = serialization.load_pem_public_key(
        public_key_pem.encode(), backend=default_backend()
    )
    if not isinstance(loaded_key, RSAPublicKey):
        raise TypeError("Expected RSA public key")
    encrypted = loaded_key.encrypt(password.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode("utf-8")


async def async_authenticate(
    username: str,
    password: str,
    region_idx: int,
    async_client: httpx.AsyncClient | None = None,
) -> AuthResult:
    """Authenticate and get bearer token."""
    async with SunSynk(server_idx=region_idx, async_client=async_client) as sdk:
        # Step 1: Get public key
        nonce = int(time.time() * 1000)
        sign_string = f"nonce={nonce}&source=sunsynk"
        sign_hash = hashlib.md5(sign_string.encode("utf-8")).hexdigest()

        _LOGGER.debug("Fetching public key from SunSynk")
        public_key_response = await sdk.authentication.get_public_key_async(
            nonce=nonce,
            source="sunsynk",
            sign=sign_hash,
        )

        public_key_base64 = public_key_response.data
        if not public_key_base64:
            raise SunSynkAuthError("Failed to get public key from SunSynk")

        # Step 2: Encrypt password
        encrypted_password = _encrypt_password(password, public_key_base64)

        # Step 3: Get bearer token
        token_nonce = int(time.time() * 1000)
        public_key_snippet = public_key_base64[:10]
        token_sign_string = f"nonce={token_nonce}&source=sunsynk{public_key_snippet}"
        token_sign = hashlib.md5(token_sign_string.encode("utf-8")).hexdigest()

        _LOGGER.debug("Authenticating with encrypted password")
        token_response = await sdk.authentication.get_bearer_token_async(
            username=username,
            password=encrypted_password,
            nonce=token_nonce,
            sign=token_sign,
            area_code="sunsynk",
            source="sunsynk",
            grant_type="password",
            client_id="csp-web",
        )

        if token_response.data and token_response.data.access_token:
            return AuthResult(
                access_token=token_response.data.access_token,
                expires_in=token_response.data.expires_in or 0,
                token_type=token_response.data.token_type or "Bearer",
            )

        raise SunSynkAuthError(f"Authentication failed: {token_response}")
