"""Provide a wrapper around JWT that caches decoding tokens.

Since we decode the same tokens over and over again
we can cache the result of the decode of valid tokens
to speed up the process.
"""
from __future__ import annotations

from datetime import timedelta
from functools import lru_cache, partial
from typing import Any

from jwt import DecodeError, PyJWS, PyJWT

from homeassistant.util.json import json_loads

JWT_TOKEN_CACHE_SIZE = 16
MAX_TOKEN_SIZE = 8192

_VERIFY_KEYS = ("signature", "exp", "nbf", "iat", "aud", "iss")

_VERIFY_OPTIONS: dict[str, Any] = {f"verify_{key}": True for key in _VERIFY_KEYS} | {
    "require": []
}
_NO_VERIFY_OPTIONS = {f"verify_{key}": False for key in _VERIFY_KEYS}


class _PyJWSWithLoadCache(PyJWS):
    """PyJWS with a dedicated load implementation."""

    @lru_cache(maxsize=JWT_TOKEN_CACHE_SIZE)
    # We only ever have a global instance of this class
    # so we do not have to worry about the LRU growing
    # each time we create a new instance.
    def _load(self, jwt: str | bytes) -> tuple[bytes, bytes, dict, bytes]:
        """Load a JWS."""
        return super()._load(jwt)


_jws = _PyJWSWithLoadCache()


@lru_cache(maxsize=JWT_TOKEN_CACHE_SIZE)
def _decode_payload(json_payload: str) -> dict[str, Any]:
    """Decode the payload from a JWS dictionary."""
    try:
        payload = json_loads(json_payload)
    except ValueError as err:
        raise DecodeError(f"Invalid payload string: {err}") from err
    if not isinstance(payload, dict):
        raise DecodeError("Invalid payload string: must be a json object")
    return payload


class _PyJWTWithVerify(PyJWT):
    """PyJWT with a fast decode implementation."""

    def decode_payload(
        self, jwt: str, key: str, options: dict[str, Any], algorithms: list[str]
    ) -> dict[str, Any]:
        """Decode a JWT's payload."""
        if len(jwt) > MAX_TOKEN_SIZE:
            # Avoid caching impossible tokens
            raise DecodeError("Token too large")
        return _decode_payload(
            _jws.decode_complete(
                jwt=jwt,
                key=key,
                algorithms=algorithms,
                options=options,
            )["payload"]
        )

    def verify_and_decode(
        self,
        jwt: str,
        key: str,
        algorithms: list[str],
        issuer: str | None = None,
        leeway: int | float | timedelta = 0,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Verify a JWT's signature and claims."""
        merged_options = {**_VERIFY_OPTIONS, **(options or {})}
        payload = self.decode_payload(
            jwt=jwt,
            key=key,
            options=merged_options,
            algorithms=algorithms,
        )
        # These should never be missing since we verify them
        # but this is an additional safeguard to make sure
        # nothing slips through.
        assert "exp" in payload, "exp claim is required"
        assert "iat" in payload, "iat claim is required"
        self._validate_claims(  # type: ignore[no-untyped-call]
            payload=payload,
            options=merged_options,
            issuer=issuer,
            leeway=leeway,
        )
        return payload


_jwt = _PyJWTWithVerify()  # type: ignore[no-untyped-call]
verify_and_decode = _jwt.verify_and_decode
unverified_hs256_token_decode = lru_cache(maxsize=JWT_TOKEN_CACHE_SIZE)(
    partial(
        _jwt.decode_payload, key="", algorithms=["HS256"], options=_NO_VERIFY_OPTIONS
    )
)

__all__ = [
    "unverified_hs256_token_decode",
    "verify_and_decode",
]
