"""Base64 encoding and decoding functions for Home Assistant templates."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


class Base64Extension(BaseTemplateExtension):
    """Jinja2 extension for base64 encoding and decoding functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the base64 extension."""
        super().__init__(
            environment,
            functions=[
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
