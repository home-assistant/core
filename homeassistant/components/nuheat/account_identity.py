"""Account identity helpers for NuHeat OAuth tokens."""

import base64
import binascii
from collections.abc import Mapping
import json
from typing import Any

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN


class InvalidAccountSubjectError(ValueError):
    """The OAuth access token has no usable account subject."""


def account_subject_from_access_token(access_token: str) -> str:
    """Return the non-empty OAuth subject from a JWT access token.

    The OAuth provider already validated and issued this token. As in Home
    Assistant's Chemelex SENZ integration, this decodes the identity claim
    without locally verifying the signature; API authorization remains the
    provider's responsibility.
    """
    try:
        payload_segment = access_token.split(".")[1]
        payload_segment += "=" * (-len(payload_segment) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_segment))
    except (
        IndexError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as err:
        raise InvalidAccountSubjectError from err

    subject = payload.get("sub") if isinstance(payload, dict) else None
    if not isinstance(subject, str) or not subject.strip():
        raise InvalidAccountSubjectError
    return subject


def account_subject_from_entry_data(data: Mapping[str, Any]) -> str:
    """Return the OAuth subject from Home Assistant config-entry data."""
    try:
        access_token = data[CONF_TOKEN][CONF_ACCESS_TOKEN]
    except (KeyError, TypeError) as err:
        raise InvalidAccountSubjectError from err
    if not isinstance(access_token, str):
        raise InvalidAccountSubjectError
    return account_subject_from_access_token(access_token)
