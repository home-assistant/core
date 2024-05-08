"""Helpers to redact Google Assistant data when logging."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.redact import async_redact_data, partial_redact

REQUEST_MSG_TO_REDACT: dict[str, Callable[[str], str]] = {
    "agentUserId": partial_redact,
    "uuid": partial_redact,
    "webhookId": partial_redact,
}

RESPONSE_MSG_TO_REDACT = REQUEST_MSG_TO_REDACT | {id: partial_redact}

SYNC_MSG_TO_REDACT = REQUEST_MSG_TO_REDACT


@callback
def async_redact_request_msg(msg: dict[str, Any]) -> dict[str, Any]:
    """Mask sensitive data in message."""
    return async_redact_data(msg, REQUEST_MSG_TO_REDACT)


@callback
def async_redact_response_msg(msg: dict[str, Any]) -> dict[str, Any]:
    """Mask sensitive data in message."""
    return async_redact_data(msg, RESPONSE_MSG_TO_REDACT)


@callback
def async_redact_sync_msg(msg: dict[str, Any]) -> dict[str, Any]:
    """Mask sensitive data in message."""
    return async_redact_data(msg, SYNC_MSG_TO_REDACT)
