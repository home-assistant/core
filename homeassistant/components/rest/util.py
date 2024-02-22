"""Helpers for RESTful API."""

import logging
from typing import Any

from jsonpath import jsonpath

from homeassistant.util.json import json_loads

_LOGGER = logging.getLogger(__name__)


def parse_json_attributes(
    value: str | None, json_attrs: list[str], json_attrs_path: str | None
) -> dict[str, Any]:
    """Parse JSON attributes."""
    if not value:
        _LOGGER.warning("Empty reply found when expecting JSON data")
        return {}

    try:
        json_dict = json_loads(value)
        if json_attrs_path is not None:
            json_dict = jsonpath(json_dict, json_attrs_path)
        # jsonpath will always store the result in json_dict[0]
        # so the next line happens to work exactly as needed to
        # find the result
        if isinstance(json_dict, list):
            json_dict = json_dict[0]
        if isinstance(json_dict, dict):
            return {k: json_dict[k] for k in json_attrs if k in json_dict}

        _LOGGER.warning(
            "JSON result was not a dictionary or list with 0th element a dictionary"
        )
    except ValueError:
        _LOGGER.warning("REST result could not be parsed as JSON")
        _LOGGER.debug("Erroneous JSON: %s", value)

    return {}
