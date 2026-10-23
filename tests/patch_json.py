"""Compatibility imports for the Home Assistant pytest helpers."""

# ruff: noqa: PLC0414

from pytest_homeassistant.patch_json import (
    Any as Any,
    functools as functools,
    json_encoder_default as json_encoder_default,
    json_helper as json_helper,
    mock as mock,
    mock_objects as mock_objects,
    orjson as orjson,
    real_json_encoder_default as real_json_encoder_default,
)
