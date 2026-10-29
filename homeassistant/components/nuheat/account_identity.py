"""Account identity helpers for NuHeat OAuth tokens."""

from collections.abc import Mapping
from typing import Any

from chemelex_nuheat import (
    InvalidAccountSubjectError,
    account_subject_from_access_token,
)

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN

__all__ = ["InvalidAccountSubjectError", "account_subject_from_entry_data"]


def account_subject_from_entry_data(data: Mapping[str, Any]) -> str:
    """Return the OAuth subject from Home Assistant config-entry data."""
    try:
        access_token = data[CONF_TOKEN][CONF_ACCESS_TOKEN]
    except (KeyError, TypeError) as err:
        raise InvalidAccountSubjectError from err
    if not isinstance(access_token, str):
        raise InvalidAccountSubjectError
    return account_subject_from_access_token(access_token)
