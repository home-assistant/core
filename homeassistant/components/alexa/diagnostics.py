"""Diagnostics helpers for Alexa."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import callback

STORAGE_ACCESS_TOKEN = "access_token"
STORAGE_REFRESH_TOKEN = "refresh_token"

TO_REDACT_LWA = {
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    STORAGE_ACCESS_TOKEN,
    STORAGE_REFRESH_TOKEN,
}

TO_REDACT_AUTH = {"correlationToken", "token"}


@callback
def async_redact_lwa_params(lwa_params: dict[str, str]) -> dict[str, str]:
    """Redact lwa_params."""
    return async_redact_data(lwa_params, TO_REDACT_LWA)


@callback
def async_redact_auth_data(mapping: Mapping[Any, Any]) -> dict[str, str]:
    """React auth data."""
    return async_redact_data(mapping, TO_REDACT_AUTH)
