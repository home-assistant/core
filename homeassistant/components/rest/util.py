"""Helpers for RESTful API."""

import logging
from typing import Any

from jsonpath import ExprSyntaxError, JSONPathTypeError, search
from orjson import JSONDecodeError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import json_loads

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def parse_json_attributes_raise_error(
    value: str | None, json_attrs: list[str], json_attrs_path: str | None
) -> dict[str, Any]:
    """Parse JSON attributes but raise an error."""
    if not value:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="no_json")

    try:
        json_dict = json_loads(value)
        if json_attrs_path is not None:
            json_dict = search(json_attrs_path, json_dict)
        if isinstance(json_dict, list) and json_dict:
            json_dict = json_dict[0]
        if isinstance(json_dict, dict):
            if result := {k: json_dict[k] for k in json_attrs if k in json_dict}:
                return result
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="attrs_not_found",
                translation_placeholders={
                    "json_attrs": ", ".join(json_attrs),
                },
            )

        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_result",
            translation_placeholders={
                "json_path": json_attrs_path or "",
            },
        )
    except (
        ValueError,
        TypeError,
        ExprSyntaxError,
        JSONPathTypeError,
        JSONDecodeError,
    ) as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="parse_error",
            translation_placeholders={
                "parse_error_message": str(ex),
            },
        ) from ex


def parse_json_attributes(
    value: str | None, json_attrs: list[str], json_attrs_path: str | None
) -> dict[str, Any]:
    """Parse JSON attributes."""
    try:
        return parse_json_attributes_raise_error(value, json_attrs, json_attrs_path)
    except HomeAssistantError as ex:
        _LOGGER.warning(str(ex))

    return {}
