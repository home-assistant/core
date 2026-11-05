"""Tests for the Home Assistant auth jwt_wrapper module."""

import jwt
import pytest

from homeassistant.auth import jwt_wrapper

JWT_KEY = "0123456789abcdef" * 4
CLAIMS = {"iss": "issuer", "iat": 1, "exp": 4102444800}
TOKEN = jwt.encode(CLAIMS, JWT_KEY, algorithm="HS256")


async def test_reject_access_token_with_impossible_large_size() -> None:
    """Test rejecting access tokens with impossible sizes."""
    with pytest.raises(jwt.DecodeError):
        jwt_wrapper.unverified_hs256_token_decode("a" * 10000)


async def test_verify_and_decode_with_cached_key() -> None:
    """Test a valid HMAC key keeps working once its check is cached."""
    for _ in range(2):
        assert (
            jwt_wrapper.verify_and_decode(
                TOKEN, JWT_KEY, algorithms=["HS256"], issuer="issuer"
            )
            == CLAIMS
        )


@pytest.mark.parametrize(
    "key",
    [
        pytest.param("", id="empty"),
        pytest.param(
            "-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQ==\n-----END PUBLIC KEY-----",
            id="pem",
        ),
        pytest.param('{"kty": "oct", "k": "c2VjcmV0"}', id="jwk"),
    ],
)
async def test_verify_and_decode_rejects_invalid_key(key: str) -> None:
    """Test invalid HMAC keys are rejected on every call, not cached."""
    for _ in range(2):
        with pytest.raises(jwt.InvalidKeyError):
            jwt_wrapper.verify_and_decode(
                TOKEN, key, algorithms=["HS256"], issuer="issuer"
            )
