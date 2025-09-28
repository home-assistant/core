"""Jinja2 extension for string processing functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode as urllib_urlencode

from homeassistant.util import slugify as slugify_util

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


class StringExtension(BaseTemplateExtension):
    """Jinja2 extension for string processing functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the string extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "ordinal",
                    self.ordinal,
                    as_filter=True,
                ),
                TemplateFunction(
                    "slugify",
                    self.slugify,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "urlencode",
                    self.urlencode,
                    as_global=True,
                ),
            ],
        )

    def ordinal(self, value: Any) -> str:
        """Perform ordinal conversion."""
        suffixes = ["th", "st", "nd", "rd"] + ["th"] * 6  # codespell:ignore nd
        return str(value) + (
            suffixes[(int(str(value)[-1])) % 10]
            if int(str(value)[-2:]) % 100 not in range(11, 14)
            else "th"
        )

    def slugify(self, value: Any, separator: str = "_") -> str:
        """Convert a string into a slug, such as what is used for entity ids."""
        return slugify_util(str(value), separator=separator)

    def urlencode(self, value: Any) -> bytes:
        """Urlencode dictionary and return as UTF-8 string."""
        return urllib_urlencode(value).encode("utf-8")
