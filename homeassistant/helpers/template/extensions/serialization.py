"""Serialization functions for Home Assistant templates."""

from __future__ import annotations

import json
import logging
from struct import error as StructError, pack, unpack_from
from typing import TYPE_CHECKING, Any

import orjson

from homeassistant.helpers.template.helpers import raise_no_default
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment

_LOGGER = logging.getLogger(__name__)

_SENTINEL = object()

_ORJSON_PASSTHROUGH_OPTIONS = (
    orjson.OPT_PASSTHROUGH_DATACLASS | orjson.OPT_PASSTHROUGH_DATETIME
)


class SerializationExtension(BaseTemplateExtension):
    """Jinja2 extension for serialization functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the serialization extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "pack",
                    self.struct_pack,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "unpack",
                    self.struct_unpack,
                    as_global=True,
                    as_filter=True,
                ),
                TemplateFunction(
                    "from_json",
                    self.from_json,
                    as_filter=True,
                ),
                TemplateFunction(
                    "to_json",
                    self.to_json,
                    as_filter=True,
                ),
                TemplateFunction(
                    "from_hex",
                    self.from_hex,
                    as_filter=True,
                ),
            ],
        )

    @staticmethod
    def struct_pack(value: Any | None, format_string: str) -> bytes | None:
        """Pack an object into a bytes object."""
        try:
            return pack(format_string, value)
        except StructError:
            _LOGGER.warning(
                (
                    "Template warning: 'pack' unable to pack object '%s' with type '%s'"
                    " and format_string '%s' see"
                    " https://docs.python.org/3/library/struct.html"
                    " for more information"
                ),
                str(value),
                type(value).__name__,
                format_string,
            )
            return None

    @staticmethod
    def struct_unpack(value: bytes, format_string: str, offset: int = 0) -> Any | None:
        """Unpack an object from bytes and return the first native object."""
        try:
            return unpack_from(format_string, value, offset)[0]
        except StructError:
            _LOGGER.warning(
                (
                    "Template warning: 'unpack' unable to unpack object '%s' with"
                    " format_string '%s' and offset %s see"
                    " https://docs.python.org/3/library/struct.html"
                    " for more information"
                ),
                value,
                format_string,
                offset,
            )
            return None

    @staticmethod
    def from_json(value: Any, default: Any = _SENTINEL) -> Any:
        """Convert a JSON string to an object."""
        try:
            return json_loads(value)
        except JSON_DECODE_EXCEPTIONS:
            if default is _SENTINEL:
                raise_no_default("from_json", value)
            return default

    @staticmethod
    def to_json(
        value: Any,
        ensure_ascii: bool = False,
        pretty_print: bool = False,
        sort_keys: bool = False,
    ) -> str:
        """Convert an object to a JSON string."""
        if ensure_ascii:
            # For those who need ascii, we can't use orjson,
            # so we fall back to the json library.
            return json.dumps(
                value,
                ensure_ascii=ensure_ascii,
                indent=2 if pretty_print else None,
                sort_keys=sort_keys,
            )

        option = (
            _ORJSON_PASSTHROUGH_OPTIONS
            # OPT_NON_STR_KEYS is added as a workaround to
            # ensure subclasses of str are allowed as dict keys
            # See: https://github.com/ijl/orjson/issues/445
            | orjson.OPT_NON_STR_KEYS
            | (orjson.OPT_INDENT_2 if pretty_print else 0)
            | (orjson.OPT_SORT_KEYS if sort_keys else 0)
        )

        return orjson.dumps(
            value,
            option=option,
            default=_to_json_default,
        ).decode("utf-8")

    @staticmethod
    def from_hex(value: str) -> bytes:
        """Perform hex string decode."""
        return bytes.fromhex(value)


def _to_json_default(obj: Any) -> None:
    """Disable custom types in json serialization."""
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
