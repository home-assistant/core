"""Provide a wrapper around JWT that caches decoding tokens.

Since we decode the same tokens over and over again
we can cache the result of the decode of valid tokens
to speed up the process.
"""

from __future__ import annotations

from collections.abc import Container, Iterable, Sequence
from datetime import timedelta
from functools import lru_cache
from typing import Any, override

from jwt import DecodeError, PyJWK, PyJWS, PyJWT
from jwt.algorithms import AllowedPublicKeys
from jwt.types import Options

from homeassistant.util.json import json_loads

JWT_TOKEN_CACHE_SIZE = 16
MAX_TOKEN_SIZE = 8192

_NO_VERIFY_OPTIONS = Options(
    verify_signature=False,
    verify_exp=False,
    verify_nbf=False,
    verify_iat=False,
    verify_aud=False,
    verify_iss=False,
    verify_sub=False,
    verify_jti=False,
    require=[],
)


class _PyJWSWithLoadCache(PyJWS):
    """PyJWS with a dedicated load implementation."""

    @lru_cache(maxsize=JWT_TOKEN_CACHE_SIZE)
    # We only ever have a global instance of this class
    # so we do not have to worry about the LRU growing
    # each time we create a new instance.
    def _load(self, jwt: str | bytes) -> tuple[bytes, bytes, dict, bytes]:
        """Load a JWS."""
        return super()._load(jwt)


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

    def __init__(self) -> None:
        """Initialize the PyJWT instance."""
        # We require exp and iat claims to be present
        super().__init__(Options(require=["exp", "iat"]))
        # Override the _jws instance with our cached version
        self._jws = _PyJWSWithLoadCache()

    def verify_and_decode(
        self,
        jwt: str,
        key: str,
        algorithms: list[str],
        issuer: str | None = None,
        leeway: float | timedelta = 0,
        options: Options | None = None,
    ) -> dict[str, Any]:
        """Verify a JWT's signature and claims."""
        return self.decode(
            jwt=jwt,
            key=key,
            algorithms=algorithms,
            issuer=issuer,
            leeway=leeway,
            options=options,
        )

    @override
    def decode(
        self,
        jwt: str | bytes,
        key: AllowedPublicKeys | PyJWK | str | bytes = "",
        algorithms: Sequence[str] | None = None,
        options: Options | None = None,
        verify: bool | None = None,
        detached_payload: bytes | None = None,
        audience: str | Iterable[str] | None = None,
        subject: str | None = None,
        issuer: str | Container[str] | None = None,
        leeway: float | timedelta = 0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Decode a JWT, verifying the signature and claims."""
        if len(jwt) > MAX_TOKEN_SIZE:
            # Avoid caching impossible tokens
            raise DecodeError("Token too large")
        return super().decode(
            jwt=jwt,
            key=key,
            algorithms=algorithms,
            options=options,
            verify=verify,
            detached_payload=detached_payload,
            audience=audience,
            subject=subject,
            issuer=issuer,
            leeway=leeway,
            **kwargs,
        )

    @override
    def _decode_payload(self, decoded: dict[str, Any]) -> dict[str, Any]:
        return _decode_payload(decoded["payload"])


_jwt = _PyJWTWithVerify()
verify_and_decode = _jwt.verify_and_decode


@lru_cache(maxsize=JWT_TOKEN_CACHE_SIZE)
def unverified_hs256_token_decode(jwt: str) -> dict[str, Any]:
    """Decode a JWT without verifying the signature."""
    return _jwt.decode(
        jwt=jwt,
        key="",
        algorithms=["HS256"],
        options=_NO_VERIFY_OPTIONS,
    )


__all__ = [
    "unverified_hs256_token_decode",
    "verify_and_decode",
]
