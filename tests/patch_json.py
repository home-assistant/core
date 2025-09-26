"""Patch JSON related functions."""

from __future__ import annotations

import functools
from typing import Any
from unittest import mock

import orjson

from homeassistant.helpers import json as json_helper

real_json_encoder_default = json_helper.json_encoder_default

mock_objects = []


def json_encoder_default(obj: Any) -> Any:
    """Convert Home Assistant objects.

    Hand other objects to the original method.
    """
    if isinstance(obj, mock.Base):
        mock_objects.append(obj)
        raise TypeError(f"Attempting to serialize mock object {obj}")
    return real_json_encoder_default(obj)


json_helper.json_encoder_default = json_encoder_default
json_helper.json_bytes = functools.partial(
    orjson.dumps, option=orjson.OPT_NON_STR_KEYS, default=json_encoder_default
)
json_helper.json_bytes_sorted = functools.partial(
    orjson.dumps,
    option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SORT_KEYS,
    default=json_encoder_default,
)
