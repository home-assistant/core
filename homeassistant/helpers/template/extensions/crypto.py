"""Cryptographic and encoding functions for Home Assistant templates."""

from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


class CryptoExtension(BaseTemplateExtension):
    """Jinja2 extension for cryptographic and encoding functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the crypto extension."""
        super().__init__(
            environment,
            functions=[
                # Hash functions (as globals and filters)
                TemplateFunction(
                    "md5", self.md5, as_global=True, as_filter=True, limited_ok=False
                ),
                TemplateFunction(
                    "sha1", self.sha1, as_global=True, as_filter=True, limited_ok=False
                ),
                TemplateFunction(
                    "sha256",
                    self.sha256,
                    as_global=True,
                    as_filter=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "sha512",
                    self.sha512,
                    as_global=True,
                    as_filter=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "base64_encode",
                    self.base64_encode,
                    as_filter=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "base64_decode",
                    self.base64_decode,
                    as_filter=True,
                    limited_ok=False,
                ),
            ],
        )

    @staticmethod
    def md5(value: str) -> str:
        """Generate md5 hash from a string."""
        return hashlib.md5(value.encode()).hexdigest()

    @staticmethod
    def sha1(value: str) -> str:
        """Generate sha1 hash from a string."""
        return hashlib.sha1(value.encode()).hexdigest()

    @staticmethod
    def sha256(value: str) -> str:
        """Generate sha256 hash from a string."""
        return hashlib.sha256(value.encode()).hexdigest()

    @staticmethod
    def sha512(value: str) -> str:
        """Generate sha512 hash from a string."""
        return hashlib.sha512(value.encode()).hexdigest()

    @staticmethod
    def base64_encode(value: str | bytes) -> str:
        """Encode a string or bytes to base64."""
        if isinstance(value, str):
            value = value.encode("utf-8")
        return base64.b64encode(value).decode("utf-8")

    @staticmethod
    def base64_decode(value: str, encoding: str | None = "utf-8") -> str | bytes:
        """Decode a base64 string."""
        decoded = base64.b64decode(value)
        if encoding is None:
            return decoded
        return decoded.decode(encoding)
